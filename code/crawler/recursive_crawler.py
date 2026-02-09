import os
import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin

# Create directory for saving scraped content
if not os.path.exists("scraped_content"):
    os.makedirs("scraped_content")

# Initialize session and tracking variables
session = requests.Session()
base_url = 'https://www.gov.za'
visited_urls = set()  # To avoid revisiting the same URLs
delay = 1  # Delay between requests (in seconds) to be respectful

def clean_filename(text):
    """Convert text to a valid filename."""
    # Remove invalid characters
    filename = re.sub(r'[\\/*?:"<>|]', "", text)
    # Replace spaces and dashes with underscores
    filename = re.sub(r'[\s-]+', "_", filename)
    # Ensure the filename isn't too long
    if len(filename) > 100:
        filename = filename[:100]
    return filename + ".txt"

def has_significant_text(soup):
    """Check if a page has significant paragraph content within the target div."""
    # Find the target div containing the main content
    target_div = soup.find('div', id='block-eco-omega-system-main')
    
    # If the target div doesn't exist, check the entire page
    if not target_div:
        paragraphs = soup.find_all('p')
    else:
        paragraphs = target_div.find_all('p')
    
    # Find paragraphs that aren't just links
    content_paragraphs = [p for p in paragraphs 
                         if p.text.strip() and 
                         (not p.find('a') or len(p.text) > len(p.find('a').text) + 10)]
    
    # Consider it a content page if there are several paragraphs with reasonable length
    has_content = len(content_paragraphs) >= 2 and sum(len(p.text) for p in content_paragraphs) > 150
    
    if has_content:
        print(f"Found content page with {len(content_paragraphs)} paragraphs")
    
    return has_content

def extract_page_content(soup, url):
    """Extract the main content from a page."""
    # Find the target div that contains the main content
    main_content = soup.find('div', id='block-eco-omega-system-main')
    
    # If the target div doesn't exist, fall back to other common content containers
    if not main_content:
        main_content = soup.find('div', class_='content') or soup.find('article') or soup
        print(f"Using fallback content container for {url}")
    
    # Get the title - first try to find h1 within the main content div
    title_tag = main_content.find('h1') if main_content else None
    if not title_tag:
        title_tag = soup.find('h1') or soup.title
    
    title = title_tag.get_text(strip=True) if title_tag else url.split('/')[-1].replace('-', ' ').title()
    
    # Extract paragraphs from the main content
    paragraphs = main_content.find_all('p') if main_content else soup.find_all('p')
    content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
    
    return title, content

def save_content_to_file(title, content, url):
    """Save the extracted content to a text file."""
    if not content.strip():
        return False  # Skip if no content
    
    filename = clean_filename(title)
    filepath = os.path.join("scraped_content", filename)
    
    with open(filepath, 'w', encoding='utf-8') as file:
        file.write(f"Title: {title}\n")
        file.write(f"Source URL: {url}\n")
        file.write(f"Date scraped: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        file.write("\n" + "="*50 + "\n\n")
        file.write(content)
    
    print(f"✓ Saved: {filename}")
    return True

def extract_links(soup, current_url):
    """Extract links only from the target div and convert to absolute URLs."""
    links = []
    
    # Find the specific div containing the links we're interested in
    target_div = soup.find('div', id='block-eco-omega-system-main')
    
    # If the target div exists, extract links only from it
    if target_div:
        for a_tag in target_div.find_all('a', href=True):
            href = a_tag['href']
            # Skip non-http links, anchors, etc.
            if href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
                continue
            
            # Convert relative URL to absolute
            full_url = urljoin(current_url, href)
            
            # Only include links within the same domain
            if full_url.startswith(base_url):
                links.append(full_url)
        
        print(f"Found {len(links)} links in target div")
    else:
        print(f"Target div 'block-eco-omega-system-main' not found on {current_url}")
    
    return links

def process_page(url):
    """Process a single page: either extract content or get child links."""
    if url in visited_urls:
        return []
    
    visited_urls.add(url)
    print(f"Processing: {url}")
    
    try:
        # Add delay to be respectful to the server
        time.sleep(delay)
        
        # Fetch the page
        response = session.get(url)
        if response.status_code != 200:
            print(f"Failed to retrieve {url}: Status code {response.status_code}")
            return []
        
        # Parse the HTML
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Check if this is a content page
        if has_significant_text(soup):
            title, content = extract_page_content(soup, url)
            save_content_to_file(title, content, url)
            return []  # No need to process further if we've found content
        else:
            # If not a content page, extract links to continue searching
            return extract_links(soup, url)
            
    except Exception as e:
        print(f"Error processing {url}: {e}")
        return []

def recursive_crawl():
    """Start the recursive crawling process from the root URL."""
    # Queue of URLs to process
    url_queue = ['https://www.gov.za/services-residents']
    
    while url_queue:
        current_url = url_queue.pop(0)  # Get next URL from queue
        
        # Process the page and get child links if not a content page
        child_links = process_page(current_url)
        
        # Add new links to the queue
        for link in child_links:
            if link not in visited_urls and link not in url_queue:
                url_queue.append(link)
        
        print(f"Queue size: {len(url_queue)} | Processed URLs: {len(visited_urls)}")

def main():
    try:
        print("Starting web crawl of South African government services...")
        print(f"Content will be saved to: {os.path.abspath('scraped_content')}")
        recursive_crawl()
        print(f"Crawl completed. Processed {len(visited_urls)} URLs.")
    except KeyboardInterrupt:
        print("\nCrawl interrupted by user.")
    except Exception as e:
        print(f"Crawl failed with error: {e}")

if __name__ == "__main__":
    main()