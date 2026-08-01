import requests
import re
import json
import time
import os
import urllib.parse

# Configuration
BASE_DOMAIN = "https://freeporno.xxx"

# Add as many categories here as you want, and specify the exact filename for each
CATEGORIES_TO_SCRAPE = [
    {"url": "https://freeporno.xxx/party", "name": "Party", "filename": "db.json"},
    {"url": "https://freeporno.xxx/medical", "name": "Medical", "filename": "db2.json"},
    {"url": "https://freeporno.xxx/japanese", "name": "Japanese", "filename": "db3.json"}
]

MAX_PAGES_TO_SCRAPE = 999
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Terminal Colors for nice output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

# Initialize a persistent requests session to handle cookies automatically
session = requests.Session()
session.headers.update({
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
    'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    'Sec-Ch-Ua-Mobile': '?0',
    'Sec-Ch-Ua-Platform': '"Windows"',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'same-origin',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})

def fetch_html(url, referer=""):
    """Fetches HTML content from a URL using the persistent session."""
    headers = {}
    if referer:
        headers['Referer'] = referer
        
    try:
        response = session.get(url, headers=headers, timeout=15, verify=False)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"{Colors.FAIL}Error fetching {url}: {e}{Colors.ENDC}")
        return None

def scrape_single_video_data(url, referer):
    """Scrapes title, poster, and direct stream URL from a video page."""
    html = fetch_html(url, referer)
    if not html:
        return False
        
    result = {
        'id': '',
        'title': '',
        'poster': '',
        'stream_url': '',
        'headers': {'Referer': url}
    }
    
    # Extract Title
    title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    if title_match:
        # Strip HTML tags
        clean_title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
        result['id'] = clean_title
        result['title'] = clean_title
        
    # Extract Poster
    poster_match = re.search(r'<meta\s+property=["\']og:image["\']\s+content=["\'](.*?)["\']', html, re.IGNORECASE)
    if poster_match:
        result['poster'] = poster_match.group(1)
    else:
        fallback_poster = re.search(r'poster=["\'](.*?)["\']', html, re.IGNORECASE)
        if fallback_poster:
            result['poster'] = fallback_poster.group(1)
            
    # Extract initial video source URL
    initial_video_url = ""
    source_match = re.search(r'<source[^>]+src=["\']([^"\']+)["\'][^>]*type=["\']video/mp4["\']', html, re.IGNORECASE)
    if source_match:
        # Unquote URL (urldecode) and remove any escaped slashes (stripslashes)
        initial_video_url = urllib.parse.unquote(source_match.group(1).replace('\\', ''))
        
    if initial_video_url:
        try:
            # Perform a HEAD request without following redirects to capture the Location header
            head_headers = {'Referer': url}
            head_response = session.head(initial_video_url, headers=head_headers, allow_redirects=False, timeout=5, verify=False)
            
            if head_response.status_code in (301, 302):
                result['stream_url'] = head_response.headers.get('Location', initial_video_url).strip()
            else:
                result['stream_url'] = initial_video_url
        except Exception:
            result['stream_url'] = initial_video_url
            
    return result

def save_to_json_file(items, category_name, file_path):
    """Saves the scraped items to a specific JSON file matching the exact PHP structure."""
    hero_items = items[:5]
    final_json_data = {
        "hero": hero_items,
        "categories": [
            {
                "name": category_name,
                "items": items
            }
        ]
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(final_json_data, f, indent=4, ensure_ascii=False)

def main():
    import warnings
    # Suppress unverified HTTPS request warnings (matches CURLOPT_SSL_VERIFYPEER = false)
    warnings.filterwarnings('ignore', message='Unverified HTTPS request')

    print(f"{Colors.HEADER}{Colors.BOLD}Starting Fast Multi-Category Scraper (Python)...{Colors.ENDC}\n" + "-"*50)

    total_all_categories_scraped = 0

    for category in CATEGORIES_TO_SCRAPE:
        start_url = category["url"]
        cat_name = category["name"]
        
        # Get the custom file name from the configuration
        custom_file_name = category.get("filename", f"{cat_name}.json")
        data_file = os.path.join(BASE_DIR, custom_file_name)

        current_page_url = start_url
        page_count = 1
        total_videos_scraped = 0
        all_items = []

        print(f"\n{Colors.HEADER}{Colors.BOLD}>>> Processing Category: {cat_name}{Colors.ENDC}")
        print(f"{Colors.BLUE}Target: {start_url}{Colors.ENDC}")
        print(f"{Colors.BLUE}Saving to: {data_file}{Colors.ENDC}\n" + "-"*50)

        while current_page_url and page_count <= MAX_PAGES_TO_SCRAPE:
            print(f"\n{Colors.WARNING}[+] Processing Page {page_count}: {current_page_url}{Colors.ENDC}")
            
            category_html = fetch_html(current_page_url, BASE_DOMAIN)
            if not category_html:
                break
                
            # Find all video links
            video_paths = re.findall(r'<a[^>]*class=["\'][^"\']*b-thumb-item__link[^"\']*["\'][^>]*href=["\'](/v[0-9]+[^"\']*)["\']', category_html, re.IGNORECASE | re.DOTALL)
            
            # Remove duplicates while preserving order
            video_paths = list(dict.fromkeys(video_paths))
            
            if not video_paths:
                print(f"{Colors.FAIL}No videos found on this page. Stopping category {cat_name}.{Colors.ENDC}")
                break
                
            print(f"Found {len(video_paths)} videos on this page. Extracting fast...")

            for index, path in enumerate(video_paths):
                video_url = urllib.parse.urljoin(BASE_DOMAIN, path)
                
                # 0.2 seconds sleep to match usleep(200000)
                time.sleep(0.2)
                
                data = scrape_single_video_data(video_url, current_page_url)
                
                if data and data.get('title'):
                    total_videos_scraped += 1
                    total_all_categories_scraped += 1
                    all_items.append(data)
                    
                    # Save dynamically after every successful scrape to the specific category file
                    save_to_json_file(all_items, cat_name, data_file)
                    
                    print(f"  {Colors.BOLD}{data['title']}{Colors.ENDC}")
                    print(f"  {Colors.BLUE}Stream Link:{Colors.ENDC} {data['stream_url']}")
                    print(f"  {Colors.GREEN}✓ Saved to {custom_file_name}{Colors.ENDC}\n")

            next_match = re.search(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>\s*<i[^>]*class=["\']icon-arrow_right["\'][^>]*></i>\s*</a>', category_html, re.IGNORECASE)
            
            if next_match:
                next_path = next_match.group(1)
                if next_path.startswith('http'):
                    current_page_url = next_path
                else:
                    current_page_url = urllib.parse.urljoin(BASE_DOMAIN, next_path)
                    
                print(f"{Colors.WARNING}--> Next Page Found: {current_page_url}{Colors.ENDC}")
                # 0.5 seconds sleep to match usleep(500000)
                time.sleep(0.5)
                page_count += 1
            else:
                current_page_url = False

        print("-" * 50)
        print(f"{Colors.GREEN}Finished Category '{cat_name}'. Saved {total_videos_scraped} videos to {custom_file_name}{Colors.ENDC}")

    print("=" * 50)
    print(f"{Colors.HEADER}{Colors.BOLD}All Scraping Complete! Total Videos Saved Across All Categories: {total_all_categories_scraped}{Colors.ENDC}")

if __name__ == "__main__":
    main()
