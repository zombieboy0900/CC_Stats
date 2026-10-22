# Run from the project root: Rscript analysis/1_improvement/firths_analysis.R [types|codes]
library(logistf)

# CC_DATA picks the data version, as in src/cc_stats/paths.py (default v2).
dataset <- Sys.getenv("CC_DATA", "v2")
# The unit (types or codes) is the one optional argument; its groups come from
# cc_units.csv, written by build_analysis.py from src/cc_stats/units.py.
args <- commandArgs(trailingOnly = TRUE)
unit <- if (length(args) > 0) args[[1]] else "types"
out_dir <- file.path("results", dataset, "1_improvement", unit)
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
analysis <- read.csv(file.path("data/derived", dataset, "cc_analysis.csv"))

# Both outcome scales, as in src/cc_stats/outcomes.py. Each result row says
# which one it is; Holm corrects within an outcome, not across both.
OUTCOMES <- c(engel = "engel_improved", ilae = "ilae_improved")

units <- read.csv(file.path("data/derived", dataset, "cc_units.csv"))
units <- units[units$unit == unit & units$main == 1, ]
if (nrow(units) == 0) stop("unknown unit ", unit)
seizure_types <- units$group
pre_columns <- units$pre_column

firths_results <- data.frame()
adjusted_results <- data.frame()

for (outcome in names(OUTCOMES)) {

    improved <- OUTCOMES[[outcome]]

    # Cohort: this outcome, LGS and pre-op seizure types all recorded.
    model_cols <- c(improved, "lgs", pre_columns)
    new <- analysis[complete.cases(analysis[model_cols]), ]
    for (i in seq_along(seizure_types)) new[[seizure_types[i]]] <- new[[pre_columns[i]]]
    new$improved <- new[[improved]]

    uni <- data.frame()
    adj <- data.frame()

    for(stype in c(seizure_types, "lgs")) {

        f <- as.formula(paste("improved ~", stype))

        fit <- logistf(f, data = new)

        uni <- rbind(uni, data.frame(
            outcome = outcome,
            predictor = stype,
            n_with = sum(new[[stype]]),
            n_without = sum(new[[stype]] == 0),
            improved_with = sum(new$improved[new[[stype]] == 1]),
            improved_without = sum(new$improved[new[[stype]] == 0]),
            OR = exp(coef(fit)[[stype]]),
            lo = exp(fit$ci.lower[[stype]]),
            hi = exp(fit$ci.upper[[stype]]),
            p = fit$prob[[stype]]
        ))

        if (stype == "lgs") next

        f_adj <- as.formula(paste("improved ~", stype, "+ lgs"))

        fit_adj <- logistf(f_adj, data = new)

        adj <- rbind(adj, data.frame(
            outcome = outcome,
            seizure_type = stype,
            type_OR = exp(coef(fit_adj)[[stype]]),
            type_lo = exp(fit_adj$ci.lower[[stype]]),
            type_hi = exp(fit_adj$ci.upper[[stype]]),
            type_p = fit_adj$prob[[stype]],
            lgs_OR = exp(coef(fit_adj)[["lgs"]]),
            lgs_lo = exp(fit_adj$ci.lower[["lgs"]]),
            lgs_hi = exp(fit_adj$ci.upper[["lgs"]]),
            lgs_p = fit_adj$prob[["lgs"]]
        ))
    }

    uni$p_holm <- p.adjust(uni$p, method = "holm")
    adj$type_p_holm <- p.adjust(adj$type_p, method = "holm")
    firths_results <- rbind(firths_results, uni)
    adjusted_results <- rbind(adjusted_results, adj)
}

firths_results[order(firths_results$outcome, firths_results$p), ]
adjusted_results[order(adjusted_results$outcome, adjusted_results$type_p), ]

write.csv(firths_results, file.path(out_dir, "firths_results.csv"), row.names = FALSE)
write.csv(adjusted_results, file.path(out_dir, "firths_results_lgs_adjusted.csv"), row.names = FALSE)
