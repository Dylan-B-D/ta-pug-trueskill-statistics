window.onload = function () {
    document.getElementById("queue").addEventListener("change", autoSubmit);
    document.getElementById("min_games").addEventListener("change", autoSubmit);

    function autoSubmit() {
        // Submit the form when the value in any control is changed
        document.querySelector(".controls-form").submit();
    }

}
