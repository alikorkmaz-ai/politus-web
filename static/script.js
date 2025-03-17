document.getElementById('apply-filters').addEventListener('click', () => {
    const formElement = document.getElementById('filter-form'); // Filtreleme formunu al
    const formData = new FormData(formElement); // Doğru formdan veri oku
    const filters = {};

    // Filtreleri JSON formatına dönüştür
    formData.forEach((value, key) => {
        if (value && value !== 'all') {
            filters[key] = value;
        }
    });

    // Yıl aralığı filtrelerini al
    const startYear = document.getElementById('publication-start-year').value;
    const endYear = document.getElementById('publication-end-year').value;

    // Eğer yıl aralığı seçildiyse, filtrelere ekle
    if (startYear) {
        filters.startYear = parseInt(startYear);
    }
    if (endYear) {
        filters.endYear = parseInt(endYear);
    }

    console.log("Gönderilen Filtreler:", filters); // Konsolda filtreleri kontrol edin

    fetch('/filter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log("Gelen Sonuçlar:", data); // Konsolda sonuçları kontrol edin
        const materialsDiv = document.getElementById('materials');
        materialsDiv.innerHTML = ''; // Önceki içerikleri temizle

        if (!Array.isArray(data) || data.length === 0) {
            materialsDiv.innerHTML = '<p>No materials found matching your criteria.</p>';
            return;
        }

        // Filtrelenen her materyali listeye ekle
        data.forEach(item => {
            let content = `
                <div class="col-md-4">
                    <div class="card shadow-sm">`;

            // **Resim Varsa Ekle**
            if (item.image) {
                content += `<img src="${item.image}" class="card-img-top" alt="Material Image">`;
            }

            content += `<div class="card-body">
                            <h5 class="card-title">${item.title || 'No Title Available'}</h5>
                            <p class="card-text">${item.description || 'No Description Available'}</p>`;

            // **Eğer `_id` varsa "Details" butonunu ekleyelim**
            if (item._id) {
                content += `<a href="/document/${item._id}" class="btn btn-sm btn-info">Details</a>`;
            } else {
                content += `<p class="text-muted">No details available</p>`;
            }

            // **Makale Linki Varsa "Original Source" Butonu Ekleyelim**
            if (item.link) {
                content += `<a href="${item.link}" target="_blank" class="btn btn-sm btn-secondary">Original Source</a>`;
            }

            // **Yıl Filtreleme Kontrolü**
            if (startYear && endYear) {
                if (item.publication_year >= startYear && item.publication_year <= endYear) {
                    content += `<p class="card-text">Published in: ${item.publication_year}</p>`;
                } else {
                    content += `<p class="card-text">Year not within selected range</p>`;
                }
            } else {
                content += `<p class="card-text">No year filter applied</p>`;  // Yıl filtresi uygulanmadıysa
            }

            content += `</div></div></div>`;
            materialsDiv.innerHTML += content;
        });
    })
    .catch(error => console.error('Error:', error));
});



// **Reset Filters Butonu**
document.getElementById('reset-filters').addEventListener('click', () => {
    // Form içindeki tüm inputları temizle
    document.querySelectorAll('.sidebar input, .sidebar select').forEach((element) => {
        if (element.type === 'checkbox' || element.type === 'radio') {
            element.checked = false; // Checkbox ve radio butonları temizle
        } else {
            element.value = ''; // Diğer inputları temizle
        }
    });

    console.log("Filters reset!"); // Debugging için log

    // Filtreleri sıfırladıktan sonra tekrar listeyi getir
    document.getElementById('apply-filters').click();
});

// **SEARCH BOX EVENT (Kelime Bazlı Arama)**
document.getElementById('search-form').addEventListener('submit', (event) => {
    event.preventDefault(); // Sayfanın yeniden yüklenmesini engelle

    const searchQuery = document.getElementById('search-input').value.trim().toLowerCase();

    fetch('/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchQuery }) // Backend'e arama terimi gönder
    })
    .then(response => response.json())
    .then(data => {
        const materialsDiv = document.getElementById('materials');
        materialsDiv.innerHTML = '';

        if (!Array.isArray(data) || data.length === 0) {
            materialsDiv.innerHTML = '<p>No documents found matching your search.</p>';
            return;
        }

        data.forEach(item => {
            let content = `
                <div class="col-md-4">
                    <div class="card shadow-sm">
                        <div class="card-body">
                            <h5 class="card-title">${item.title || 'No Title Available'}</h5>
                            <p class="card-text">${item.description || 'No Description Available'}</p>`;

            if (item.link) {
                content += `<a href="${item.link}" target="_blank" class="btn btn-sm btn-primary">Open Document</a>`;
            }

            content += `</div></div></div>`;
            materialsDiv.innerHTML += content;
        });
    })
    .catch(error => console.error('Error:', error));
});

// Chatbot sayfasına yönlendirme fonksiyonu
function openChatbot() {
    window.location.href = "/chatbot";  // Chatbot sayfasına yönlendir
}


async function sendMessage() {
    let userInput = document.getElementById("userInput").value;
    let chatBox = document.getElementById("chatBox");
    let loading = document.getElementById("loading");

    if (userInput.trim() === "") return;

    let userMessage = `<div class="text-end"><div class="user-message">${userInput}</div></div>`;
    chatBox.innerHTML += userMessage;
    document.getElementById("userInput").value = "";
    loading.style.display = "block";  // Yüklenme animasyonunu göster
    chatBox.scrollTop = chatBox.scrollHeight;

    let response = await fetch("/query", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userInput })
    });

    let data = await response.json();
    loading.style.display = "none";  // Yüklenme animasyonunu gizle

    let botMessage = `<div class="text-start"><div class="bot-message">${data.answer}</div></div>`;
    chatBox.innerHTML += botMessage;

    if (data.sources.length > 0) {
        let sourcesMessage = `<div class="text-start"><div class="bot-message"><small>📚 Kaynaklar: ${data.sources.join(", ")}</small></div></div>`;
        chatBox.innerHTML += sourcesMessage;
    }

    chatBox.scrollTop = chatBox.scrollHeight;
}

fetch("/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query: userInput }),
})
.then(response => response.json())
.then(data => {
    document.getElementById("chatbox").innerHTML += "<p>" + data.answer + "</p>";
})
.catch(error => console.error("Error:", error));
