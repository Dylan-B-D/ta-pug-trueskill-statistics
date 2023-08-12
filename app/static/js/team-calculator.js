function moveToTeam(teamId) {
    $('.ranking-table tr.selected').each(function () {
        let playerName = $(this).find('td:nth-child(2)').text();
        let playerId = $(this).data('id');
        let playerTrueskill = parseFloat($(this).find('td:nth-child(3)').text());
        let playerMu = parseFloat($(this).find('td:nth-child(4)').text());
        let playerSigma = parseFloat($(this).find('td:nth-child(5)').text());

        let listItem = `<li data-id="${playerId}" data-trueskill="${playerTrueskill}" data-mu="${playerMu}" data-sigma="${playerSigma}"><span class="player-name">${playerName}</span> <button class="remove-player">-</button></li>`;
        $(`#${teamId}-list`).append(listItem);

        // Add the player to the "Last Match Played" UI
        updateMatchUI(teamId, playerName, playerId, playerTrueskill, playerMu, playerSigma);

        $(this).addClass('greyed-out').removeClass('selected clickable');
        updatePlayerClickability();
        updateWinProbabilities();
        updateMatchStats(teamId);
    });
}

function updateWinProbabilities() {
    let team1_count = $('#team1-list li').length;
    let team2_count = $('#team2-list li').length;

    if (team1_count > 0 && team2_count === 0) {
        setWinChances(100, 0);
    } else if (team1_count === 0 && team2_count > 0) {
        setWinChances(0, 100);
    } else if (team1_count > 0 && team2_count > 0) {
        // Use the existing method to calculate win probability
        calculateWinProbability();
    }
}

function calculateWinProbability() {
    let team1_ids = [];
    let team2_ids = [];

    $('#team1-list li').each(function () {
        team1_ids.push($(this).data('id'));
    });

    $('#team2-list li').each(function () {
        team2_ids.push($(this).data('id'));
    });

    $.post("/calculate_probability", { team1: team1_ids, team2: team2_ids }, function (data) {
        let team1Chance = parseFloat(data.win_probability);
        let team2Chance = 100 - team1Chance;

        setWinChances(team1Chance, team2Chance);
    });
}

function setWinChances(team1Chance, team2Chance) {
    // Update the display values for "Calculated Match" UI
    $("#calculated-teams-container .win-prob-container span:first-child").text(`${team1Chance.toFixed(2)}%`);
    $("#calculated-teams-container .win-prob-container span:last-child").text(`${team2Chance.toFixed(2)}%`);

    // Update the bar width for "Calculated Match" UI
    $("#calculated-teams-container .team1-prob").css("width", `${team1Chance}%`);

    // Determine colors and styles based on win chances
    if (Math.abs(team1Chance - team2Chance) <= 2) {
        $("#calculated-teams-container td:first-child ul, #calculated-teams-container td:last-child ul").removeClass('win loss tie').addClass('tie');
        $("#calculated-teams-container .win-prob-container span").css("font-weight", "normal");
    } else {
        if (team1Chance > team2Chance) {
            $("#calculated-teams-container td:first-child ul").removeClass('tie loss').addClass('win');
            $("#calculated-teams-container td:last-child ul").removeClass('tie win').addClass('loss');
            $("#calculated-teams-container .win-prob-container span:first-child").css("font-weight", "bold");
            $("#calculated-teams-container .win-prob-container span:last-child").css("font-weight", "normal");
            $("#calculated-teams-container .win-prob-bar").removeClass('team2-favored').addClass('team1-favored');
        } else {
            $("#calculated-teams-container td:first-child ul").removeClass('tie win').addClass('loss');
            $("#calculated-teams-container td:last-child ul").removeClass('tie loss').addClass('win');
            $("#calculated-teams-container .win-prob-container span:first-child").css("font-weight", "normal");
            $("#calculated-teams-container .win-prob-container span:last-child").css("font-weight", "bold");
            $("#calculated-teams-container .win-prob-bar").removeClass('team1-favored').addClass('team2-favored');
        }
    }
}




function updateMatchUI(teamId, playerName, playerId, trueskill, mu, sigma) {
    let teamSlot;
    if (teamId === "team1") {
        teamSlot = $(".match-container td:first-child ul"); // Select the first <ul> for Team 1
    } else {
        teamSlot = $(".match-container td:last-child ul"); // Select the last <ul> for Team 2
    }

    let slotFound = false;
    teamSlot.find('li').each(function() {
        if ($(this).text() === "-" && !slotFound) {
            $(this).html(`${playerName} <button class="remove-match-player" data-id="${playerId}">-</button>`);
            slotFound = true;
        }
    });
}



$('#rebalance-teams').on('click', function () {
    let allPlayers = [];

    // Gather all the players from both teams
    $('#team1-list li, #team2-list li').each(function () {
        let playerId = $(this).data('id');
        let playerTrueskill = $(this).data('trueskill');
        let playerMu = $(this).data('mu');
        let playerSigma = $(this).data('sigma');
        let playerName = $(this).find('.player-name').text();
        allPlayers.push({
            id: playerId, 
            trueskill: playerTrueskill, 
            mu: playerMu,
            sigma: playerSigma,
            name: playerName
        });
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
                    rebalancedTeam1.push({
                        id: nextPlayer.id, 
                        trueskill: nextPlayer.trueskill, 
                        mu: nextPlayer.mu, 
                        sigma: nextPlayer.sigma,
                        name: nextPlayer.name
                    });                    
        } else if (rebalancedTeam2.length < 7) {
            rebalancedTeam2.push({
                id: nextPlayer.id, 
                trueskill: nextPlayer.trueskill, 
                mu: nextPlayer.mu, 
                sigma: nextPlayer.sigma,
                name: nextPlayer.name
            });
            
        }

        balanceTeams(players);
    }

    function sumTrueskill(team) {
        return team.reduce((sum, player) => sum + player.trueskill, 0);
    }

    balanceTeams([...allPlayers]);

    // Clear the rebalanced teams containers
    $('#rebalanced-team1-list li, #rebalanced-team2-list li').text('-');

    // Add players to the rebalanced teams containers using original hidden team containers
    rebalancedTeam1.forEach(player => {
        let playerName = $(`#team1-list li[data-id="${player.id}"], #team2-list li[data-id="${player.id}"]`).find('.player-name').text();
        let nextSlot = $('#rebalanced-team1-list li').filter(function() {
            return $(this).text() === '-';
        }).first();
    
        if (nextSlot.length > 0) {
            nextSlot.text(playerName);
        }
    });
    
    rebalancedTeam2.forEach(player => {
        let playerName = $(`#team1-list li[data-id="${player.id}"], #team2-list li[data-id="${player.id}"]`).find('.player-name').text();
        let nextSlot = $('#rebalanced-team2-list li').filter(function() {
            return $(this).text() === '-';
        }).first();
    
        if (nextSlot.length > 0) {
            nextSlot.text(playerName);
        }
    });
    
    updateRebalancedMatchStats(rebalancedTeam1, "rebalanced-team1-list");
    updateRebalancedMatchStats(rebalancedTeam2, "rebalanced-team2-list");

    // Calculate win chance for rebalanced teams
    let team1_ids = rebalancedTeam1.map(player => player.id);
    let team2_ids = rebalancedTeam2.map(player => player.id);

    $.post("/calculate_probability", { team1: team1_ids, team2: team2_ids }, function (data) {
        let team1Chance = parseFloat(data.win_probability);
        let team2Chance = 100 - team1Chance;
        // Update the display values for "Rebalanced Match" UI
        $("#rebalanced-teams-container .rebalanced-win-prob-container span:first-child").text(`${team1Chance.toFixed(2)}%`);
        $("#rebalanced-teams-container .rebalanced-win-prob-container span:last-child").text(`${team2Chance.toFixed(2)}%`);

        // Update the bar width for "Rebalanced Match" UI
        $("#rebalanced-teams-container .rebalanced-team1-prob").css("width", `${team1Chance}%`);
        $('#rebalanced-team1-win-chance').text(`${team1Chance.toFixed(2)}%`);
        $('#rebalanced-team2-win-chance').text(`${team2Chance.toFixed(2)}%`);
        $(".win-prob-container .team1-prob").css("width", `${team1Chance}%`);

        // Update colors for "Rebalanced Match" UI
        if (Math.abs(team1Chance - team2Chance) <= 2) {
            $("#rebalanced-teams-container td:first-child ul, #rebalanced-teams-container td:last-child ul").removeClass('win loss tie').addClass('tie');
            $("#rebalanced-teams-container .win-prob-container span").css("font-weight", "normal");
        } else {
            if (team1Chance > team2Chance) {
                $("#rebalanced-teams-container td:first-child ul").removeClass('tie loss').addClass('win');
                $("#rebalanced-teams-container td:last-child ul").removeClass('tie win').addClass('loss');
                $("#rebalanced-teams-container .win-prob-container span:first-child").css("font-weight", "bold");
                $("#rebalanced-teams-container .win-prob-container span:last-child").css("font-weight", "normal");
                $("#rebalanced-teams-container .win-prob-bar").removeClass('team2-favored').addClass('team1-favored');
            } else {
                $("#rebalanced-teams-container td:first-child ul").removeClass('tie win').addClass('loss');
                $("#rebalanced-teams-container td:last-child ul").removeClass('tie loss').addClass('win');
                $("#rebalanced-teams-container .win-prob-container span:first-child").css("font-weight", "normal");
                $("#rebalanced-teams-container .win-prob-container span:last-child").css("font-weight", "bold");
                $("#rebalanced-teams-container .win-prob-bar").removeClass('team1-favored').addClass('team2-favored');
            }
        }
    });
});

function updateRebalancedMatchStats(rebalancedTeam, teamContainerId) {
    let totalTrueskill = 0;
    let totalMu = 0;
    let totalSigma = 0;
    let count = rebalancedTeam.length;

    rebalancedTeam.forEach(player => {
        totalTrueskill += player.trueskill;
        totalMu += player.mu;
        totalSigma += player.sigma;
    });

    let avgTrueskill = count > 0 ? (totalTrueskill / count).toFixed(2) : 0;
    let avgMu = count > 0 ? (totalMu / count).toFixed(2) : 0;
    let avgSigma = count > 0 ? (totalSigma / count).toFixed(2) : 0;

    if (teamContainerId === "rebalanced-team1-list") {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:first-child").text(avgTrueskill);
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:nth-child(3)").text(avgMu);
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:last-child").text(avgSigma);
    } else {
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:first-child").text(avgTrueskill);
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:nth-child(3)").text(avgMu);
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:last-child").text(avgSigma);
    }
}


// Remove player from a team
$(document).on('click', '.remove-match-player', function () {
    let playerRow = $(this).closest('li');
    let playerId = $(this).data('id');

    // Use the playerId to find the corresponding row in the ranking table
    let rankingRow = $('.ranking-table tr[data-id="' + playerId + '"]');
    if (rankingRow.length > 0) {
        rankingRow.removeClass('greyed-out').addClass('clickable');
    } else {
        console.error("Player ranking row NOT found for player ID: " + playerId);
    }

    // Remove the player from the main team list 
    $(`#team1-list li[data-id="${playerId}"], #team2-list li[data-id="${playerId}"]`).remove();
    
    // Set it back to the placeholder in the "Last Match Played" UI
    playerRow.text('-');

    // Update the statistics for both teams
    updateMatchStats('team1');
    updateMatchStats('team2');
    
    // Update player clickability and win probabilities
    updatePlayerClickability();
    updateWinProbabilities();
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
    $(".match-container td:first-child ul, .match-container td:last-child ul").addClass('tie');
});

function updateMatchStats(teamId) {
    let teamSlot;
    let totalTrueskill = 0;
    let totalMu = 0;
    let totalSigma = 0;
    let count = 0;

    if (teamId === "team1") {
        teamSlot = $("#team1-list li"); 
    } else {
        teamSlot = $("#team2-list li"); 
    }

    teamSlot.each(function() {
        totalTrueskill += $(this).data('trueskill');
        totalMu += $(this).data('mu');
        totalSigma += $(this).data('sigma');
        count++;
    });

    let avgTrueskill = count > 0 ? (totalTrueskill / count).toFixed(2) : 0;
    let avgMu = count > 0 ? (totalMu / count).toFixed(2) : 0;
    let avgSigma = count > 0 ? (totalSigma / count).toFixed(2) : 0;

    if (teamId === "team1") {
        $(".match-container .stats-container.left span:first-child").text(avgTrueskill);
        $(".match-container .stats-container.left span:nth-child(3)").text(avgMu);
        $(".match-container .stats-container.left span:last-child").text(avgSigma);
    } else {
        $(".match-container .stats-container.right span:first-child").text(avgTrueskill);
        $(".match-container .stats-container.right span:nth-child(3)").text(avgMu);
        $(".match-container .stats-container.right span:last-child").text(avgSigma);
    }
}