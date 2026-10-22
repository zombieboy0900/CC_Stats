# Run from the project root: Rscript analysis/0_cohort/firths_covariates.R
library(logistf)

# CC_DATA picks the data version, as in src/cc_stats/paths.py (default v2).
dataset <- Sys.getenv("CC_DATA", "v2")
out_dir <- file.path("results", dataset, "0_cohort")
dir.create(out_dir, recursive = TRUE, showWarnings = FALSE)
analysis <- read.csv(file.path("data/derived", dataset, "cc_analysis.csv"))

# Both outcome scales, as in src/cc_stats/outcomes.py. Holm corrects within
# an outcome, not across both.
OUTCOMES <- c(engel = "engel_improved", ilae = "ilae_improved")

# The number of core seizure types is modelled in 2_disappearance/count_change_firth.R
predictors <- c("sex", "age_at_cc")

covariate_results <- data.frame()

for (outcome in names(OUTCOMES)) {

    improved <- OUTCOMES[[outcome]]

    # Cohort: this outcome and every predictor recorded.
    new <- analysis[complete.cases(analysis[c(improved, predictors)]), ]
    new$sex <- as.integer(new$sex == "Male")  # 1 = male
    new$improved <- new[[improved]]

    results <- data.frame()

    for(pred in predictors) {

        f <- as.formula(paste("improved ~", pred))

        fit <- logistf(f, data = new)

        results <- rbind(results, data.frame(
            outcome = outcome,
            predictor = pred,
            n = nrow(new),
            not_improved = sum(new$improved == 0),
            mean_improved = mean(new[[pred]][new$improved == 1]),
            mean_not_improved = mean(new[[pred]][new$improved == 0]),
            OR = exp(coef(fit)[[pred]]),
            lo = exp(fit$ci.lower[[pred]]),
            hi = exp(fit$ci.upper[[pred]]),
            p = fit$prob[[pred]]
        ))
    }

    results$p_holm <- p.adjust(results$p, method = "holm")
    covariate_results <- rbind(covariate_results, results)
    print(table(sex = new$sex, improved = new$improved))
}

covariate_results[order(covariate_results$outcome, covariate_results$p), ]

write.csv(covariate_results, file.path(out_dir, "firths_results_covariates.csv"), row.names = FALSE)
