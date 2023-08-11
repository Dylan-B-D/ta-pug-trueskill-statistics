function moveToTeam(teamId) {
    $('.ranking-table tr.selected').each(function () {
        let playerName = $(this).find('td:nth-child(2)').text();
        let playerId = $(this).data('id');
        let playerTrueskill = parseFloat($(this).find('td:nth-child(3)').text());
        let playerMu = parseFloat($(this).find('td:nth-child(4)').text());
        let playerSigma = parseFloat($(this).find('td:nth-child(5)').text());

        let listItem = `<li data-id="${playerId}" data-trueskill="${playerTrueskill}" data-mu="${playerMu}" data-sigma="${playerSigma}"><span class="player-name">${playerName}</span> <button class="remove-player">Remove</button></li>`;


        $(`#${teamId}-list`).append(listItem);
        $(this).addClass('greyed-out').removeClass('selected clickable');
        updatePlayerClickability();
    });
}

$('#rebalance-teams').on('click', function () {
    let allPlayers = [];

    // Gather all the players from both teams
    $('#team1-list li, #team2-list li').each(function () {
        let playerId = $(this).data('id');
        let playerTrueskill = $(this).data('trueskill');
        let playerName = $(this).find('.player-name').text();
        allPlayers.push({ id: playerId, trueskill: playerTrueskill, name: playerName });
    });

    // Sort players by trueskill rating
    allPlayers.sort((a, b) => b.trueskill - a.trueskill);

    let rebalancedTeam1 = [];
    let rebalancedTeam2 = [];

    // Recursive function to balance the teams
    function balanceTeams(players) {
        if (players.length === 0) return;

        let nextPlayer = players.shift();

        if (rebalancedTeam1.length < 7 &&
            (rebalancedTeam1.length < rebalancedTeam2.length ||
                sumTrueskill(rebalancedTeam1) <= sumTrueskill(rebalancedTeam2))) {
            rebalancedTeam1.push(nextPlayer);
        } else if (rebalancedTeam2.length < 7) {
            rebalancedTeam2.push(nextPlayer);
        }

        balanceTeams(players);
    }

    function sumTrueskill(team) {
        return team.reduce((sum, player) => sum + player.trueskill, 0);
    }

    balanceTeams([...allPlayers]);

    // Clear the rebalanced teams containers
    $('#rebalanced-team1-list, #rebalanced-team2-list').empty();

    // Add players to the rebalanced teams containers
    rebalancedTeam1.forEach(player => {
        $('#rebalanced-team1-list').append(`<li data-id="${player.id}">${player.name}</li>`);
    });

    rebalancedTeam2.forEach(player => {
        $('#rebalanced-team2-list').append(`<li data-id="${player.id}">${player.name}</li>`);
    });

    // Calculate win chance for rebalanced teams
    let team1_ids = rebalancedTeam1.map(player => player.id);
    let team2_ids = rebalancedTeam2.map(player => player.id);

    $.post("/calculate_probability", { team1: team1_ids, team2: team2_ids }, function (data) {
        $('#rebalanced-win-chance').text(data.win_probability + "% chance for Team 1");
    });
});


// Remove player from a team
$(document).on('click', '.remove-player', function () {
    let playerRow = $(this).closest('li');
    let playerId = playerRow.data('id');

    // Use the playerId to find the corresponding row in the ranking table
    let rankingRow = $('.ranking-table tr[data-id="' + playerId + '"]');
    if (rankingRow.length > 0) {
        rankingRow.removeClass('greyed-out').addClass('clickable');
    } else {
        console.error("Player ranking row NOT found for player ID: " + playerId);
    }

    playerRow.remove();
    updatePlayerClickability(); updatePlayerClickability();
});
$('#calculate-win-probability').on('click', function () {
    let team1_ids = [];
    let team2_ids = [];

    $('#team1-list li').each(function () {
        team1_ids.push($(this).data('id'));
    });

    $('#team2-list li').each(function () {
        team2_ids.push($(this).data('id'));
    });

    $.post("/calculate_probability", { team1: team1_ids, team2: team2_ids }, function (data) {
        $('#win-chance-display').text(data.win_probability + '%');
    });
});

function updatePlayerClickability() {
    // Get all player IDs currently in teams
    let playersInTeams = [];
    $('.team-container ul li').each(function () {
        playersInTeams.push($(this).data('id'));
    });

    // For each row in the ranking table, set clickability based on the team list
    $('.ranking-table tr').not(':first').each(function () {
        if (playersInTeams.includes($(this).data('id'))) {
            $(this).removeClass('clickable').addClass('greyed-out');
        } else {
            $(this).removeClass('greyed-out').addClass('clickable');
        }
    });
}



$(document).ready(function () {
    $('.ranking-table tr').not(':first').addClass('clickable');
    // Attach keyup event to the search input
    $('#player_search').on('keyup', function () {
        // Get the current value of the search input
        let value = $(this).val().toLowerCase();

        // Filter the table rows based on the input value
        $('.ranking-table tr').not(':first').filter(function () {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1)
        });
    });

    // Toggle row selection when a table row is clicked
    // Only rows from the player ranking table and not the header
    $('.ranking-table tr').not(':first').on('click', function () {
        if ($(this).hasClass('clickable')) {
            $(this).toggleClass('selected');
        }
    });


    // Attach event handlers to the move buttons
    $('#move_to_team1').on('click', function () {
        moveToTeam('team1');
    });

    $('#move_to_team2').on('click', function () {
        moveToTeam('team2');
    });
    updatePlayerClickability();
});