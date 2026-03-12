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
                console.log(indexProviderOptions);
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
                    display: ["STI", "AWORLDS", "SREIT"].includes(othersIndex)
                        ? "none"
                        : "block",
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
