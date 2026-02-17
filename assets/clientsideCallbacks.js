window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
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
});
