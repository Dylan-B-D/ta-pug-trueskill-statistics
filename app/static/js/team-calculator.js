$(document).ready(function () {
    initializeEventHandlers();
    updatePlayerClickability();
    setInitialMatchStyles();
});

function initializeEventHandlers() {
    $('#player_search').on('keyup', handlePlayerSearch);
    $('.ranking-table tr').not(':first').on('click', handlePlayerRowClick);
    $('#move_to_team1').on('click', () => moveToTeam('team1'));
    $('#move_to_team2').on('click', () => moveToTeam('team2'));
    $('#rebalance-teams').on('click', handleRebalanceTeams);
    $(document).on('click', '.remove-match-player', handleRemovePlayer);
    $('#calculate-win-probability').on('click', handleCalculateWinProbability);
}

function handlePlayerSearch() {
    let value = $(this).val().toLowerCase();
    $('.ranking-table tr').not(':first').each(function() {
        toggleVisibility($(this), $(this).text().toLowerCase().indexOf(value) > -1);
    });
}

function toggleVisibility(element, condition) {
    element.toggle(condition);
}

function handlePlayerRowClick() {
    if ($(this).hasClass('clickable')) {
        $(this).toggleClass('selected');
    }
}

function setInitialMatchStyles() {
    $(".match-container td:first-child ul, .match-container td:last-child ul").addClass('tie');
}

function handleRebalanceTeams() {
    let allPlayers = gatherAllPlayers();
    allPlayers.sort((a, b) => b.trueskill - a.trueskill);

    let rebalancedTeam1 = [];
    let rebalancedTeam2 = [];
    balanceTeams([...allPlayers], rebalancedTeam1, rebalancedTeam2);

    updateRebalancedTeamsUI(rebalancedTeam1, rebalancedTeam2);
    calculateRebalancedWinChances(rebalancedTeam1, rebalancedTeam2);
}

function handleRemovePlayer() {
    let playerId = $(this).data('id');
    let rankingRow = $('.ranking-table tr[data-id="' + playerId + '"]');

    toggleClass(rankingRow, 'greyed-out', false);
    toggleClass(rankingRow, 'clickable', true);

    $(`#team1-list li[data-id="${playerId}"], #team2-list li[data-id="${playerId}"]`).remove();
    $(this).text('-');

    updateMatchStats('team1');
    updateMatchStats('team2');
    updatePlayerClickability();
    updateWinProbabilities();
}

function toggleClass(element, className, condition) {
    if (condition) {
        element.addClass(className);
    } else {
        element.removeClass(className);
    }
}

function handleCalculateWinProbability() {
    let team1_ids = gatherTeamPlayerIDs('team1');
    let team2_ids = gatherTeamPlayerIDs('team2');

    $.post("/calculate_probability", { team1: team1_ids, team2: team2_ids }, function (data) {
        $('#win-chance-display').text(data.win_probability + '%');
    });
}

function gatherTeamPlayerIDs(teamId) {
    return $(`#${teamId}-list li`).map(function () {
        return $(this).data('id');
    }).get();
}

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
    compareStats(".match-container .stats-container.left", ".match-container .stats-container.right");
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
function sumTrueskill(team) {
        return team.reduce((sum, player) => sum + player.trueskill, 0);
    }
function balanceTeams(players, rebalancedTeam1, rebalancedTeam2) {
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

    balanceTeams(players, rebalancedTeam1, rebalancedTeam2);
}

// Function to gather all players from both teams
function gatherAllPlayers() {
    let allPlayers = [];
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
    return allPlayers;
}

// Function to update the rebalanced teams' UI
function updateRebalancedTeamsUI(rebalancedTeam1, rebalancedTeam2) {
    // Clear the rebalanced teams containers
    $('#rebalanced-team1-list li, #rebalanced-team2-list li').text('-');

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
}

// Function to calculate win chances and update the UI
function calculateRebalancedWinChances(rebalancedTeam1, rebalancedTeam2) {
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
        compareStats("#rebalanced-teams-container .rebalanced-stats-container.left", "#rebalanced-teams-container .rebalanced-stats-container.right");

        if (Math.abs(team1Chance - team2Chance) <= 2) {
            $("#rebalanced-teams-container td:first-child ul, #rebalanced-teams-container td:last-child ul").removeClass('win loss').addClass('tie');
            $("#rebalanced-teams-container .rebalanced-win-prob-container span").css("font-weight", "normal");
        } else {
            if (team1Chance > team2Chance) {
                $("#rebalanced-teams-container td:first-child ul").removeClass('tie loss').addClass('win');
                $("#rebalanced-teams-container td:last-child ul").removeClass('tie win').addClass('loss');
                $("#rebalanced-teams-container .rebalanced-win-prob-container span:first-child").css("font-weight", "bold");
                $("#rebalanced-teams-container .rebalanced-win-prob-container span:last-child").css("font-weight", "normal");
                $("#rebalanced-teams-container .rebalanced-win-prob-bar").removeClass('team2-favored').addClass('team1-favored');
            } else {
                $("#rebalanced-teams-container td:first-child ul").removeClass('tie win').addClass('loss');
                $("#rebalanced-teams-container td:last-child ul").removeClass('tie loss').addClass('win');
                $("#rebalanced-teams-container .rebalanced-win-prob-container span:first-child").css("font-weight", "normal");
                $("#rebalanced-teams-container .rebalanced-win-prob-container span:last-child").css("font-weight", "bold");
                $("#rebalanced-teams-container .rebalanced-win-prob-bar").removeClass('team1-favored').addClass('team2-favored');
            }
        }
    });
}

function compareStats(statsContainerLeft, statsContainerRight) {
    // Extract average stats for both teams
    let team1TS = parseFloat($(statsContainerLeft + " span:first-child").text());
    let team1Mu = parseFloat($(statsContainerLeft + " span:nth-child(3)").text());
    let team1Sigma = parseFloat($(statsContainerLeft + " span:last-child").text());

    let team2TS = parseFloat($(statsContainerRight + " span:first-child").text());
    let team2Mu = parseFloat($(statsContainerRight + " span:nth-child(3)").text());
    let team2Sigma = parseFloat($(statsContainerRight + " span:last-child").text());

    // Compare Trueskill and set bold for the higher value
    if (team1TS > team2TS) {
        $(statsContainerLeft + " span:first-child").css("font-weight", "bold");
        $(statsContainerRight + " span:first-child").css("font-weight", "normal");
    } else if (team1TS < team2TS) {
        $(statsContainerLeft + " span:first-child").css("font-weight", "normal");
        $(statsContainerRight + " span:first-child").css("font-weight", "bold");
    } else {
        $(statsContainerLeft + " span:first-child, " + statsContainerRight + " span:first-child").css("font-weight", "normal");
    }

    // Compare Mu and set bold for the higher value
    if (team1Mu > team2Mu) {
        $(statsContainerLeft + " span:nth-child(3)").css("font-weight", "bold");
        $(statsContainerRight + " span:nth-child(3)").css("font-weight", "normal");
    } else if (team1Mu < team2Mu) {
        $(statsContainerLeft + " span:nth-child(3)").css("font-weight", "normal");
        $(statsContainerRight + " span:nth-child(3)").css("font-weight", "bold");
    } else {
        $(statsContainerLeft + " span:nth-child(3), " + statsContainerRight + " span:nth-child(3)").css("font-weight", "normal");
    }

    // Compare Sigma and set bold for the lower value
    if (team1Sigma < team2Sigma) {
        $(statsContainerLeft + " span:last-child").css("font-weight", "bold");
        $(statsContainerRight + " span:last-child").css("font-weight", "normal");
    } else if (team1Sigma > team2Sigma) {
        $(statsContainerLeft + " span:last-child").css("font-weight", "normal");
        $(statsContainerRight + " span:last-child").css("font-weight", "bold");
    } else {
        $(statsContainerLeft + " span:last-child, " + statsContainerRight + " span:last-child").css("font-weight", "normal");
    }
}


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