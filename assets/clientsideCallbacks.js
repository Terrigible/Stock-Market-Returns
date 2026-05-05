window.dash_clientside = Object.assign({}, window.dash_clientside, {
    state: {
        updateLastLayoutStore:
            /**
             * Updates a store of layout configurations, typically used for preserving
             * the last known layout for different Y-axis variables.
             *
             * @param {object} figure An object containing a 'layout' property (e.g., a Plotly figure object).
             * @param {string} yVar The key (Y-axis variable name) under which to store the layout.
             * @returns {object} The updated layout store object.
             */
            function (figure, yVar) {
                if (yVar === "price") {
                    return JSON.parse(JSON.stringify(figure.layout));
                }
            },
    },
    visibility: {
        updateSecuritySelectionVisibility:
            /**
             * Shows the container matching the selected security type.
             *
             * @param {string} securityType The selected security type value.
             * @param {Array} securityTypeOptions List of security type options.
             * @returns {Array} Array of style objects for each container.
             */
            function (securityType, securityTypeOptions) {
                return securityTypeOptions.map(function (option) {
                    return {
                        display: securityType === option ? "block" : "none",
                    };
                });
            },

        updateIndexSelectionVisibility:
            /**
             * Shows the container matching the selected index provider.
             *
             * @param {string} indexProvider The selected index provider value.
             * @param {Object} indexProviderOptions Dictionary of index provider options.
             * @returns {Array} Array of style objects for each container.
             */
            function (indexProvider, indexProviderOptions) {
                return Object.keys(indexProviderOptions).map(function (option) {
                    return {
                        display: indexProvider === option ? "block" : "none",
                    };
                });
            },

        updateOthersTaxTreatmentSelectionVisibility:
            /**
             * Hides tax treatment selection for certain indices.
             *
             * @param {string} othersIndex The selected others index value.
             * @returns {Object} Style object for the container.
             */
            function (othersIndex) {
                return {
                    display: ["SREIT"].includes(othersIndex) ? "none" : "block",
                };
            },

        updateFredDurationSelectionVisibility:
            /**
             * Hides duration selection for FFR index.
             *
             * @param {string} fredIndex The selected FRED index value.
             * @returns {Object} Style object for the container.
             */
            function (fredIndex) {
                return { display: fredIndex === "FFR" ? "none" : "block" };
            },

        updateMasDurationSelectionVisibility:
            /**
             * Hides duration selection for SORA index.
             *
             * @param {string} masIndex The selected MAS index value.
             * @returns {Object} Style object for the container.
             */
            function (masIndex) {
                return { display: masIndex === "SORA" ? "none" : "block" };
            },

        updateSelectionVisibility:
            /**
             * Helper function to compute visibility styles based on y_var.
             *
             * @param {string} yVar The selected y-axis variable.
             * @returns {Array} Array of style objects for containers.
             */
            function (yVar) {
                var show = { display: "block" };
                var hide = { display: "none" };

                var priceVisibility = yVar === "price" ? show : hide;
                var returnSelectionStyle =
                    yVar === "rolling_returns" || yVar === "calendar_returns"
                        ? show
                        : hide;
                var rollingReturnSelectionStyle =
                    yVar === "rolling_returns" ? show : hide;
                var calendarReturnSelectionStyle =
                    yVar === "calendar_returns" ? show : hide;

                return [
                    priceVisibility,
                    returnSelectionStyle,
                    rollingReturnSelectionStyle,
                    calendarReturnSelectionStyle,
                ];
            },

        updateStrategyDrawdownTypeVisibility:
            /**
             * Shows drawdown type container for max_drawdown selection.
             *
             * @param {string} yVar The selected y-axis variable.
             * @returns {Object} Style object for the container.
             */
            function (yVar) {
                return { display: yVar === "max_drawdown" ? "block" : "none" };
            },

        updateRollingReturnsDistributionChartTypeVisibility:
            /**
             * Shows chart type container for distribution presentation.
             *
             * @param {string} presentation The selected presentation type.
             * @returns {Object} Style object for the container.
             */
            function (presentation) {
                return { display: presentation === "dist" ? "block" : "none" };
            },
    },
    options: {
        updateSecuritySelectionOptions:
            /**
             * Updates portfolio security selection based on selected securities options.
             *
             * @param {Object} securityOptions Dictionary of security options.
             * @returns {Array} [options, value]
             */
            function (securityOptions) {
                var keys = Object.keys(securityOptions);
                var newValue =
                    keys.length === 1
                        ? keys[0]
                        : window.dash_clientside.no_update;
                return [securityOptions, newValue];
            },

        updateBaselineSecuritySelectionOptions:
            /**
             * Updates baseline selection options based on selected items.
             *
             * @param {Array} selectedItems List of selected item keys.
             * @param {Object} selectedItemsOptions Dictionary of selected item options.
             * @param {string} baselineItem Current baseline item value.
             * @returns {Array} [options, value, disabled]
             */
            function (selectedItems, selectedItemsOptions, baselineItem) {
                var options = { None: "None" };
                for (var key in selectedItemsOptions) {
                    if (selectedItems.includes(key)) {
                        options[key] = selectedItemsOptions[key];
                    }
                }
                var newValue =
                    selectedItems.includes(baselineItem) &&
                    selectedItems.length > 1
                        ? baselineItem
                        : "None";
                var disabled = selectedItems.length <= 1;
                return [options, newValue, disabled];
            },

        updateStrategyPortfolioOptions:
            /**
             * Updates strategy portfolio selections based on available portfolios.
             *
             * @param {Object} portfolioOptions Dictionary of portfolio options.
             * @returns {Array} [options1, options2, value1, value2]
             */
            function (portfolioOptions) {
                var keys = Object.keys(portfolioOptions);
                var selectedValue =
                    keys.length === 1
                        ? keys[0]
                        : window.dash_clientside.no_update;
                return [
                    portfolioOptions,
                    portfolioOptions,
                    selectedValue,
                    selectedValue,
                ];
            },
    },
    update_values: {
        portfolioWeightsSum:
            /**
             * Calculates the sum of portfolio weights.
             *
             * @param {Array} allocationStrings Array of JSON-encoded allocation strings.
             * @returns {string} Display string with sum of weights.
             */
            function (allocationStrings) {
                if (!allocationStrings || allocationStrings.length === 0) {
                    return "Sum of Weights: ";
                }
                var total = 0;
                for (var i = 0; i < allocationStrings.length; i++) {
                    var allocation = JSON.parse(allocationStrings[i]);
                    for (var key in allocation) {
                        total += allocation[key];
                    }
                }
                return "Sum of Weights: " + total + "%";
            },
    },
    toast: {
        updateToast:
            /**
             * Updates toast children and visibility based on toast store data.
             *
             * @param {string|null} toast The toast message from the store.
             * @returns {Array} Array containing toast children and is_open state.
             */
            function (toast) {
                return [toast, toast ? true : false];
            },
    },
});
