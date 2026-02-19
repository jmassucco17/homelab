let searchTimeout = null;
const searchInput = document.getElementById('location-search');
const searchResults = document.getElementById('search-results');

searchInput.addEventListener('input', handleSearch);

async function handleSearch(e) {
    const query = e.target.value.trim();
    
    clearTimeout(searchTimeout);
    
    if (query.length < 2) {
        searchResults.innerHTML = '';
        searchResults.classList.remove('show');
        return;
    }
    
    searchTimeout = setTimeout(async () => {
        try {
            const response = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
            const results = await response.json();
            
            displaySearchResults(results);
        } catch (error) {
            console.error('Search error:', error);
            searchResults.innerHTML = '<div class="search-result-item">Error searching for locations</div>';
            searchResults.classList.add('show');
        }
    }, 300);
}

function displaySearchResults(results) {
    if (!results || results.length === 0) {
        searchResults.innerHTML = '<div class="search-result-item">No results found</div>';
        searchResults.classList.add('show');
        return;
    }
    
    searchResults.innerHTML = results.map(result => `
        <div class="search-result-item" 
             onclick='addLocationFromSearch(${JSON.stringify(result)})'>
            ${result.name}
        </div>
    `).join('');
    
    searchResults.classList.add('show');
}

document.addEventListener('click', (e) => {
    if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
        searchResults.classList.remove('show');
    }
});
