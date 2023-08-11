window.onload = function () {
    // Attach "change" event listener to the date input fields
    document.getElementById("start_date").addEventListener("blur", autoSubmit);
    document.getElementById("end_date").addEventListener("blur", autoSubmit);


    // Attach "click" event listener to the reset button
    document.getElementById("reset_button").addEventListener("click", resetDates);

    function autoSubmit() {
        // Submit the form when the value in the date picker is changed
        this.form.submit();
    }
    document.getElementById("queue").addEventListener("change", autoSubmit);

    document.getElementById("min_games").addEventListener("change", autoSubmit);
    document.getElementById("min-games-form").addEventListener("submit", function (event) {
        // Prevent the form from being submitted normally
        event.preventDefault();

        // Submit the form via JavaScript
        this.submit();
    });

    function resetDates() {
        // Prevent the form from being submitted
        event.preventDefault();

        // Set the start date to November 1, 2018
        document.getElementById("start_date").value = "2018-11-01";

        // Set the end date to the current date
        let today = new Date();
        let dd = String(today.getDate()).padStart(2, '0');
        let mm = String(today.getMonth() + 1).padStart(2, '0');
        let yyyy = today.getFullYear();
        today = yyyy + '-' + mm + '-' + dd;
        document.getElementById("end_date").value = today;

        // Submit the form
        this.form.submit();
    }
}