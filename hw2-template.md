# **Homework 2: Data Discovery, Problem Framing & Visual Critique**

**Student Name:** Batman Whiteside 
**Date:** 09/10/26


## **Part 1: Dataset Selection**

* **Dataset Name:** Daily Activity Logs

* **Source & URL:** [GitHub repository](https://github.com/batmankatman/pythonics-prod-program-ai4)

* **Overview:** This dataset contains 70 waking-day recordings from five 14-day trial pairs. Each recording is a reverse-chronological activity log with 4,010 timed activity rows plus 70 lights-out markers; the analysis derives 70 daily category-total rows and 65 overnight sleep intervals. The categorical variables are Productive (P), Routine (R), Eat (E), Social (S), Workout (W), Fun (F), and God/ministry (GOD); continuous variables are activity durations, category totals, total recorded activity time, and sleep minutes; temporal variables include date, weekday, waking-day order, and within-day timestamps. There is no spatial variable.

* **Interest Statement:** This dataset actually comes from my personal experiment recording daily activities from waking time to lights out. It supports personal discovery of how time is actually allocated, rather than comparing a planned schedule with reality only at the level of daily averages. Treating waking hours as the unit of analysis also preserves activities that cross midnight without falsely assigning them to a new calendar day.

## **Part 2: Problem Framing & Analytic Tasks**

**Why It’s a Good Visualization Problem**

The log contains 70 waking-day recordings across five 14-day trial pairs. Each recording is a sequence of activities whose durations are calculated from adjacent timestamps, so ordinary means can hide timing, composition, weekday effects, and tradeoffs between categories. The data are also compositional: more time in one category can leave less available for another. A visual interface is therefore needed to compare many categories across time while preserving the waking-day definition rather than treating midnight as a boundary, too.

**Three Core Analytic Tasks**

* **Task 1 (Composition / Trend):** Compare how Productive, Routine, Eat, Social, Workout, Fun, and God time are allocated across all 70 waking-day recordings, both in minutes and as shares of each day’s recorded activity.
* **Task 2 (Categorical Comparison):** Compare weekday composition and seven-day period totals while preserving the distinction between repeated weekday observations and complete trial periods.
* **Task 3 (Relationship / Tradeoff):** Identify whether above-average time in one category tends to coincide with below- or above-average time in another, and distinguish raw associations from relationships that remain after accounting for weekday and total recorded time.

These tasks correspond to the heatmap and daily-composition chart for Task 1, the weekday stacked chart and weekly correlation matrix for Task 2, and the daily category pair matrix plus residual correlation matrix for Task 3. The Q-Q plots and sleep/productivity plot are supporting diagnostics rather than the primary portfolio charts.

## **Part 3 & 4: Visualization Portfolio & Critiques**

### **1\. Waking-Day Composition Heatmap**

[![Waking-day composition heatmap](https://raw.githubusercontent.com/batmankatman/pythonics-prod-program-ai4/main/analysis_output/01_composition_heatmap.svg)](https://raw.githubusercontent.com/batmankatman/pythonics-prod-program-ai4/main/analysis_output/01_composition_heatmap.svg)

* **Target Task:** Task 1, composition and trend.

* **Rationale & Critique:** This heatmap keeps all 70 waking-day recordings in chronological order and places the seven categories in stable columns. Each cell shows the exact duration while opacity supports rapid scanning, so the reader can see both small recurring activities and large changes in Productive or Fun time without estimating bar lengths. The additional total-hours column distinguishes a genuinely different composition from a day with simply more recorded activity. The percentage row at the bottom summarizes how the entire dataset’s recorded time is distributed across categories. Routine uses indigo, giving it a distinct visual identity from the other categories. The chart’s important semantic choice is that every row comes from one waking-day recording: durations are calculated from that day’s activity sequence, not from literal calendar-day boundaries. The main limitation is vertical density. Seventy rows require a tall display, and color intensity is less precise than the printed minute values. The exact labels and total column mitigate that limitation, while the chart remains useful for locating clusters, gaps, and unusually composition-heavy days.

### **2\. All-Data Category Totals by Weekday**

[![Category totals by weekday](https://raw.githubusercontent.com/batmankatman/pythonics-prod-program-ai4/main/analysis_output/10_weekday_stacked_bar.svg)](https://raw.githubusercontent.com/batmankatman/pythonics-prod-program-ai4/main/analysis_output/10_weekday_stacked_bar.svg)

* **Target Task:** Task 2, categorical comparison.

* **Rationale & Critique:** This stacked bar chart aggregates the ten occurrences of each weekday and shows the total minutes for all seven categories. Each segment is labeled in hours, so the viewer can read both the overall weekday total and the contribution of each category without relying only on color. The chart highlights broad behavioral differences: weekdays can be compared as complete compositions, while the stable category order makes the stacks easy to scan. It complements the heatmap by reducing 70 rows to seven grouped summaries. Stacking is appropriate for the total-time question, though segments away from the baseline are less accurate for precise cross-weekday comparison. The labels and consistent colors reduce that perceptual cost. This chart should not be interpreted as seven independent correlation observations; each weekday total is an aggregate of ten days and discards trial-pair variation. Its strength is descriptive comparison of typical weekday allocation, not causal inference.

### **3\. Flawed Visualization Example: Residual Category Correlation Matrix**

[![Flawed residual correlation matrix](https://raw.githubusercontent.com/batmankatman/pythonics-prod-program-ai4/main/analysis_output/13_residual_category_correlation.svg)](https://raw.githubusercontent.com/batmankatman/pythonics-prod-program-ai4/main/analysis_output/13_residual_category_correlation.svg)

* **Target Task:** Task 3, adjusted category relationships.

* **Rationale & Critique:** This matrix looks precise because it reports coefficients to two decimal places, but it is a poor primary visualization for this dataset. Each category is residualized against weekday and total recorded category time, even though total recorded time is itself built from the categories being compared. That adjustment can manufacture or suppress associations through the compositional constraint rather than reveal a meaningful behavioral relationship. The matrix also hides the underlying 70 observations, uncertainty, sample dependence, and the fact that the residual correlations are not causal effects. Its diverging colors invite quick ranking of positive and negative values without showing whether a relationship is stable across the five trial pairs. A better approach is the daily category pair matrix, which retains every day, places mean reference lines directly in each panel, and lets the reader inspect whether above-average and below-average quadrants are populated. The residual matrix is useful as a sensitivity check, but presenting it as the main answer would overstate what the data can support.

