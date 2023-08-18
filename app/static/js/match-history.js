$(document).ready(function(){
    $( "#player_search" ).autocomplete({
        source: "/autocomplete_player",
        minLength: 1,
        select: function(event, ui) {
            $("#player_search").val(ui.item.value); // set the value of the search input
            $(".player-search-form").submit();     // submit the form
        }
    });
    $("#toggle-metrics-btn").click(function() {
        $(".accuracy-container").toggle(); // This toggles the display of the accuracy-container
    });
});
