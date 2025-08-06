window.dash_clientside = Object.assign({}, window.dash_clientside, {
    clientside: {
        updateLastLayoutStore:
            /**
            * Updates a store of layout configurations, typically used for preserving
            * the last known layout for different Y-axis variables.
            *
            * @param {object} figure An object containing a 'layout' property (e.g., a Plotly figure object).
            * @param {object | undefined} oldData An object representing the previous layout store,
            *                                  or null if it's the first update.
            * @param {string} yVar The key (Y-axis variable name) under which to store the layout.
            * @returns {object} The updated layout store object.
            */
            function (figure, oldData, yVar) {
                if (typeof oldData === 'undefined') {
                    // If oldData is undefined, initialize a new object with the current layout
                    // under the specified yVar key.
                    return {
                        [yVar]: JSON.parse(JSON.stringify(figure.layout)),
                    };
                } else {
                    // If oldData exists, update the specific yVar's layout in the existing object.
                    oldData[yVar] = JSON.parse(JSON.stringify(figure.layout));
                    return oldData;
                }
            }
    }
});