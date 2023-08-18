window.onload = function () {
    document.getElementById("queue").addEventListener("change", autoSubmit);
    document.getElementById("min_games").addEventListener("change", autoSubmit);

    function autoSubmit() {
        document.querySelector(".controls-form").submit();
    }

    let playerRows = document.querySelectorAll(".table-container table tr:not(:first-child)");
    playerRows.forEach(row => {
        row.addEventListener("mouseover", function() {
            highlightSimilarPlayers(row);
        });
        row.addEventListener("mouseout", function() {
            removeHighlight();
        });
    });
}

function highlightSimilarPlayers(hoveredRow) {
    let hoveredMu = parseFloat(hoveredRow.querySelector("td:nth-child(4)").textContent);
    let hoveredSigma = parseFloat(hoveredRow.querySelector("td:nth-child(5)").textContent);
    let lowerBound = hoveredMu - 2 * hoveredSigma;
    let upperBound = hoveredMu + 2 * hoveredSigma;

    let playerRows = document.querySelectorAll(".table-container table tr:not(:first-child)");
    playerRows.forEach(row => {
        let currentMu = parseFloat(row.querySelector("td:nth-child(4)").textContent);
        if (currentMu >= lowerBound && currentMu <= upperBound) {
            let intensity = calculateIntensity(hoveredMu, currentMu, hoveredSigma);
            row.style.backgroundColor = `rgba(101, 136, 168, ${intensity})`;  
        } else {
            row.style.backgroundColor = "";  
        }
    });
}

function removeHighlight() {
    let playerRows = document.querySelectorAll(".table-container table tr:not(:first-child)");
    playerRows.forEach(row => {
        row.style.backgroundColor = ""; 
    });
}

// New function to calculate intensity
function calculateIntensity(hoveredMu, currentMu, sigma) {
    // Calculate the absolute distance between hoveredMu and currentMu
    let distance = Math.abs(hoveredMu - currentMu);
    
    // Normalize the distance with respect to 2*sigma
    let normalizedDistance = distance / (2 * sigma);

    // Calculate the intensity (closer players will have intensity closer to 1, farther players will have intensity closer to 0)
    let intensity = 1 - normalizedDistance;

    return intensity;
}

