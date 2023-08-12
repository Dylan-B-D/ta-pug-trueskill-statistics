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
    // Event handler for the reset buttons
    $(document).on('click', '.reset-team-btn', function() {
        console.log("Reset button clicked!");
    
        let team = $(this).data('team');
    
        // Get all the player IDs in the team
        let playerIds = $(`#${team}-list li`).map(function() {
            return $(this).data('id');
        }).get();
    
        // Remove each player from the team
        for (let playerId of playerIds) {
            removePlayerFromTeam(playerId);
        }
    });

    // Event handler for the move buttons inside the table rows
    $(document).on('click', '.ranking-table .move-button', function () {
        let teamTarget = $(this).data('target');
        let row = $(this).closest('tr');
        if (row.hasClass('clickable')) {
            if ($(`#${teamTarget}-list li`).length < 7) {
                row.addClass('selected');
                moveToTeam(teamTarget);
            } else {
                alert(`Team ${teamTarget === 'team1' ? '1' : '2'} is already full!`);
            }
        }
    });

    $('#copy-rebalanced-match').on('click', function() {
        let team1Players = [];
        let team2Players = [];
        
        $('#rebalanced-team1-list li').each(function() {
            team1Players.push($(this).text());
        });
        
        $('#rebalanced-team2-list li').each(function() {
            team2Players.push($(this).text());
        });
    
        // Extract statistics
        let team1TS = $("#rebalanced-teams-container .rebalanced-stats-container.left span:first-child").text();
        let team1Mu = $("#rebalanced-teams-container .rebalanced-stats-container.left span:nth-child(3)").text();
        let team1Sigma = $("#rebalanced-teams-container .rebalanced-stats-container.left span:last-child").text();
        let team2TS = $("#rebalanced-teams-container .rebalanced-stats-container.right span:first-child").text();
        let team2Mu = $("#rebalanced-teams-container .rebalanced-stats-container.right span:nth-child(3)").text();
        let team2Sigma = $("#rebalanced-teams-container .rebalanced-stats-container.right span:last-child").text();
    
        let team1Chance = $("#rebalanced-teams-container .rebalanced-win-prob-container span:first-child").text();
        let team2Chance = $("#rebalanced-teams-container .rebalanced-win-prob-container span:last-child").text();
    
        // Constructing the ASCII table with Discord-specific formatting (bold)
        let separator = "+------------------------+------------------------+";
        let formattedText = "```" + "\n"; // Start code block for Discord
        formattedText += separator + "\n";
        formattedText += "| **Team 1**              | **Team 2**              |\n";
        formattedText += separator + "\n";
        formattedText += `| Win Chance: ${team1Chance.padEnd(12)} | Win Chance: ${team2Chance.padEnd(12)} |\n`;
        formattedText += `| TS: ${team1TS.padEnd(18)} | TS: ${team2TS.padEnd(18)} |\n`;
        formattedText += `| Mu: ${team1Mu.padEnd(19)} | Mu: ${team2Mu.padEnd(19)} |\n`;
        formattedText += `| Sigma: ${team1Sigma.padEnd(16)} | Sigma: ${team2Sigma.padEnd(16)} |\n`;
        formattedText += separator + "\n";
        
        for (let i = 0; i < Math.max(team1Players.length, team2Players.length); i++) {
            let player1 = team1Players[i] || ""; // Fallback to empty string if player doesn't exist
            let player2 = team2Players[i] || "";
            formattedText += `| ${player1.padEnd(24)} | ${player2.padEnd(24)} |\n`; // Pad player names to align nicely
        }
        
        formattedText += separator;
        formattedText += "\n```"; // End code block for Discord
    
        // Copy the formatted text to clipboard
        copyToClipboard(formattedText);
    
        alert("Match copied to clipboard in Discord table format!");
    });
    
});

function copyToClipboard(text) {
    var $temp = $("<textarea>");
    $("body").append($temp);
    $temp.val(text).select();
    document.execCommand("copy");
    $temp.remove();
}


function removePlayerFromTeam(playerId) {
    let playerRow = $(`.remove-match-player[data-id="${playerId}"]`).closest('li');
    
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
}

function moveToTeam(teamId) {
    let teamCapacity = 7; // Maximum number of players in a team

    $('.ranking-table tr.selected').each(function () {
        // Exit the loop if the team is full
        if ($(`#${teamId}-list li`).length >= teamCapacity) {
            alert(`Team ${teamId === 'team1' ? '1' : '2'} is already full!`);
            return false; // This will break the .each() loop
        }

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

    if (team1_count === 0 && team2_count === 0) {
        setWinChances(50, 50);
    } else if (team1_count > 0 && team2_count === 0) {
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
    compareTeamStats();
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

function compareTeamStats() {
    // Extract average stats for both teams
    let team1TS = parseFloat($(".match-container .stats-container.left span:first-child").text());
    let team1Mu = parseFloat($(".match-container .stats-container.left span:nth-child(3)").text());
    let team1Sigma = parseFloat($(".match-container .stats-container.left span:last-child").text());

    let team2TS = parseFloat($(".match-container .stats-container.right span:first-child").text());
    let team2Mu = parseFloat($(".match-container .stats-container.right span:nth-child(3)").text());
    let team2Sigma = parseFloat($(".match-container .stats-container.right span:last-child").text());

    // Compare Trueskill and set bold for the higher value
    if (team1TS > team2TS) {
        $(".match-container .stats-container.left span:first-child").css("font-weight", "bold");
        $(".match-container .stats-container.right span:first-child").css("font-weight", "normal");
    } else if (team1TS < team2TS) {
        $(".match-container .stats-container.left span:first-child").css("font-weight", "normal");
        $(".match-container .stats-container.right span:first-child").css("font-weight", "bold");
    } else {
        $(".match-container .stats-container.left span:first-child, .match-container .stats-container.right span:first-child").css("font-weight", "normal");
    }

    // Compare Mu and set bold for the higher value
    if (team1Mu > team2Mu) {
        $(".match-container .stats-container.left span:nth-child(3)").css("font-weight", "bold");
        $(".match-container .stats-container.right span:nth-child(3)").css("font-weight", "normal");
    } else if (team1Mu < team2Mu) {
        $(".match-container .stats-container.left span:nth-child(3)").css("font-weight", "normal");
        $(".match-container .stats-container.right span:nth-child(3)").css("font-weight", "bold");
    } else {
        $(".match-container .stats-container.left span:nth-child(3), .match-container .stats-container.right span:nth-child(3)").css("font-weight", "normal");
    }

    // Compare Sigma and set bold for the lower value
    if (team1Sigma < team2Sigma) {
        $(".match-container .stats-container.left span:last-child").css("font-weight", "bold");
        $(".match-container .stats-container.right span:last-child").css("font-weight", "normal");
    } else if (team1Sigma > team2Sigma) {
        $(".match-container .stats-container.left span:last-child").css("font-weight", "normal");
        $(".match-container .stats-container.right span:last-child").css("font-weight", "bold");
    } else {
        $(".match-container .stats-container.left span:last-child, .match-container .stats-container.right span:last-child").css("font-weight", "normal");
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
            $(this).html(`${playerName} <button class="remove-match-player" data-id="${playerId}">X</button>`);
            slotFound = true;
        }
    });
}
function sumTrueskill(team) {
        return team.reduce((sum, player) => sum + player.trueskill, 0);
}
function generateCombinations(players, teamSize, startIndex = 0, currentTeam = []) {
    if (currentTeam.length === teamSize) {
        return [currentTeam];
    }
    if (startIndex === players.length) {
        return [];
    }

    const withCurrentPlayer = generateCombinations(players, teamSize, startIndex + 1, currentTeam.concat(players[startIndex]));
    const withoutCurrentPlayer = generateCombinations(players, teamSize, startIndex + 1, currentTeam);

    return withCurrentPlayer.concat(withoutCurrentPlayer);
}

function balanceTeamsOptimized(players) {
    let bestDifference = Infinity;
    let bestTeam1 = [];
    let bestTeam2 = [];

    const maxTeamSize = Math.min(7, Math.floor(players.length / 2));
    for (let teamSize = 1; teamSize <= maxTeamSize; teamSize++) {
        const team1Combinations = generateCombinations(players, teamSize);

        for (const team1 of team1Combinations) {
            const team2 = players.filter(player => !team1.includes(player));
            const difference = Math.abs(sumTrueskill(team1) - sumTrueskill(team2));

            if (difference < bestDifference) {
                bestDifference = difference;
                bestTeam1 = team1;
                bestTeam2 = team2;
            }
        }
    }

    return {
        team1: bestTeam1,
        team2: bestTeam2
    };
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
        compareRebalancedTeamStats();

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

$('#rebalance-teams').on('click', function () {
    let allPlayers = gatherAllPlayers();

    // Sort players by trueskill rating
    allPlayers.sort((a, b) => b.trueskill - a.trueskill);

    const { team1: rebalancedTeam1, team2: rebalancedTeam2 } = balanceTeamsOptimized(allPlayers);

    updateRebalancedTeamsUI(rebalancedTeam1, rebalancedTeam2);
    calculateRebalancedWinChances(rebalancedTeam1, rebalancedTeam2);
});


function compareRebalancedTeamStats() {
    // Extract average stats for both rebalanced teams
    let team1TS = parseFloat($("#rebalanced-teams-container .rebalanced-stats-container.left span:first-child").text());
    let team1Mu = parseFloat($("#rebalanced-teams-container .rebalanced-stats-container.left span:nth-child(3)").text());
    let team1Sigma = parseFloat($("#rebalanced-teams-container .rebalanced-stats-container.left span:last-child").text());

    let team2TS = parseFloat($("#rebalanced-teams-container .rebalanced-stats-container.right span:first-child").text());
    let team2Mu = parseFloat($("#rebalanced-teams-container .rebalanced-stats-container.right span:nth-child(3)").text());
    let team2Sigma = parseFloat($("#rebalanced-teams-container .rebalanced-stats-container.right span:last-child").text());

    // Compare Trueskill and set bold for the higher value
    if (team1TS > team2TS) {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:first-child").css("font-weight", "bold");
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:first-child").css("font-weight", "normal");
    } else if (team1TS < team2TS) {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:first-child").css("font-weight", "normal");
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:first-child").css("font-weight", "bold");
    } else {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:first-child, #rebalanced-teams-container .rebalanced-stats-container.right span:first-child").css("font-weight", "normal");
    }

    // Compare Mu and set bold for the higher value
    if (team1Mu > team2Mu) {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:nth-child(3)").css("font-weight", "bold");
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:nth-child(3)").css("font-weight", "normal");
    } else if (team1Mu < team2Mu) {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:nth-child(3)").css("font-weight", "normal");
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:nth-child(3)").css("font-weight", "bold");
    } else {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:nth-child(3), #rebalanced-teams-container .rebalanced-stats-container.right span:nth-child(3)").css("font-weight", "normal");
    }

    // Compare Sigma and set bold for the lower value
    if (team1Sigma < team2Sigma) {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:last-child").css("font-weight", "bold");
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:last-child").css("font-weight", "normal");
    } else if (team1Sigma > team2Sigma) {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:last-child").css("font-weight", "normal");
        $("#rebalanced-teams-container .rebalanced-stats-container.right span:last-child").css("font-weight", "bold");
    } else {
        $("#rebalanced-teams-container .rebalanced-stats-container.left span:last-child, #rebalanced-teams-container .rebalanced-stats-container.right span:last-child").css("font-weight", "normal");
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