async function fetchEarnings() {
    try {
        const baseUrl = "http://192.168.88.253:8000";

        // Fetch earnings for hotspot users
        const hotspotRes = await fetch(`${baseUrl}/payments/total/hotspot`);
        const hotspotData = await hotspotRes.json();
        console.log(hotspotData)

        // Fetch earnings for PPPoE users
        const pppRes = await fetch(`${baseUrl}/payments/total/pppoe`);
        const pppData = await pppRes.json();
        console.log(pppData.total_payment)

        // Update UI
        document.querySelector('.cards .card:nth-child(1) p').textContent = `Ksh ${hotspotData.total_payment} : Hotspot`;
        document.querySelector('.cards .card:nth-child(1) h2').textContent = `Ksh ${pppData.total_payment} : PPPoE`;
    } catch (error) {
        console.error('Error fetching earnings:', error);
    }
}

fetchEarnings();

async function fetchUsers() {
    try {
        const baseUrl = "http://192.168.88.253:8000";

        // Fetch PPPoE users
        const pppRes = await fetch(`${baseUrl}/ppp_users`);
        const pppUsers = await pppRes.json();
        console.log(pppUsers)

        // Fetch Hotspot users
        const hotspotRes = await fetch(`${baseUrl}/hotspot_users`);
        const hotspotUsers = await hotspotRes.json()
       console.log((count(hotspotUsers)));

        // Update UI
        document.querySelector('.cards .card:nth-child(3) p').textContent = 
            `${pppUsers.count()}/${pppUsers.total} Active (${((pppUsers.count() / pppUsers.count()) * 100).toFixed(1)}%)`;

        document.querySelector('.cards .card:nth-child(4) p').textContent = `${hotspotUsers.length()} Active`;

    } catch (error) {
        console.error('Error fetching users:', error);
    }
}

fetchUsers();

async function fetchLogs() {
    try {
        const baseUrl = "http://192.168.88.253:8000";
        const response = await fetch(`${baseUrl}/payments`);
        const payments = await response.json();

        const paymentsTable = document.querySelector("#recent-activity tbody");
        paymentsTable.innerHTML = "";  // Clear table before inserting new payments

        payments.forEach(payment => {
            let row = `<tr>
                <td>${payment.id}</td>
                <td>${payment.invoice}</td>
                <td>${payment.user_type}</td>
            </tr>`;
            logsTable.innerHTML += row;
        });

    } catch (error) {
        console.error("Error fetching logs:", error);
    }
}

fetchLogs();

async function fetchRxTxData() {
    try {
        const baseUrl = "http://192.168.88.253:8000";
        const response = await fetch(`${baseUrl}/rt_rx_data`);
        const data = await response.json();

        // Assuming data contains "rx" and "tx" values
        updateGraph(data.rx, data.tx);
        
    } catch (error) {
        console.error("Error fetching RX/TX data:", error);
    }
}

function updateGraph(rx, tx) {
    const ctx = document.getElementById('rx-tx-chart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: ["1m", "2m", "3m", "4m", "5m"],
            datasets: [
                { label: "RX", data: rx, borderColor: "blue", fill: false },
                { label: "TX", data: tx, borderColor: "red", fill: false }
            ]
        }
    });
}

fetchRxTxData();
