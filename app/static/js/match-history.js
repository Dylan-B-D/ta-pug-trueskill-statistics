$(document).ready(function(){
    $( "#player_search" ).autocomplete({
        source: "/autocomplete_player",
        minLength: 1,
        select: function(event, ui) {
            window.location.href = "/match-history?player_search=" + ui.item.value;
        }
    });
});
