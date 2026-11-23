#!/usr/bin/env Rscript
# Reviewed entry point. Base R only. No packages, no network, no randomness.
# Estimand: within each arm, pooled mean daily steps = sum(steps_sum) / sum(n_people).
# Printed means use two decimal places. The three fixture arms divide evenly at that scale.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 2L) {
  stop("usage: Rscript --vanilla analyze.R INPUT_CSV OUTPUT_CSV")
}

input_path <- args[[1]]
output_path <- args[[2]]
required <- c("group_id", "arm", "n_people", "steps_sum")
frame <- utils::read.csv(input_path, stringsAsFactors = FALSE, check.names = FALSE)
if (!identical(names(frame), required)) {
  stop("input columns must be exactly: ", paste(required, collapse = ", "))
}
if (nrow(frame) < 1L) {
  stop("input has no data rows")
}

arms <- sort(unique(frame$arm))
rows <- vector("list", length(arms))
for (i in seq_along(arms)) {
  arm <- arms[[i]]
  part <- frame[frame$arm == arm, , drop = FALSE]
  people <- sum(part$n_people)
  if (!is.finite(people) || people < 1) {
    stop("arm ", arm, " has no people; the pooled mean is undefined")
  }
  steps <- sum(part$steps_sum)
  rows[[i]] <- data.frame(
    endpoint_id = arm,
    estimand = "pooled_mean_daily_steps",
    unit = "steps_per_person_per_day",
    n_people = as.integer(people),
    n_groups = as.integer(nrow(part)),
    mean_steps = sprintf("%.2f", steps / people),
    stringsAsFactors = FALSE
  )
}

out <- do.call(rbind, rows)
utils::write.csv(out, output_path, row.names = FALSE, quote = TRUE)
