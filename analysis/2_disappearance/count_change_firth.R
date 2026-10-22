# Run from the project root, after count_change.py (with the same unit):
#   Rscript analysis/2_disappearance/count_change_firth.R [types|codes]
library(logistf)

# CC_DATA picks the data version, as in src/cc_stats/paths.py (default v2).
dataset <- Sys.getenv("CC_DATA", "v2")
# The unit (types or codes, as in src/cc_stats/units.py) is the one optional argument
args <- commandArgs(trailingOnly = TRUE)
unit <- if (length(args) > 0) args[[1]] else "types"
out_dir <- file.path("results", dataset, "2_disappearance", unit)
# One row per patient per outcome, written by count_change.py
counts <- read.csv(file.path(out_dir, "count_change_by_patient.csv"))

# One predictor per model: improved ~ count, for each outcome.
firth_results <- data.frame()

for (outcome in unique(counts$outcome)) {

    patients <- counts[counts$outcome == outcome, ]

    for (predictor in c("n_before", "n_after", "net_loss")) {

        f <- as.formula(paste("improved ~", predictor))

        fit <- logistf(f, data = patients)

        firth_results <- rbind(firth_results, data.frame(
            outcome = outcome,
            predictor = predictor,
            n = nrow(patients),
            not_improved = sum(patients$improved == 0),
            OR = exp(coef(fit)[[predictor]]),
            lo = exp(fit$ci.lower[[predictor]]),
            hi = exp(fit$ci.upper[[predictor]]),
            p = fit$prob[[predictor]]
        ))
    }
}

firth_results

write.csv(firth_results, file.path(out_dir, "count_change_firth.csv"), row.names = FALSE)
