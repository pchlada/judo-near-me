#!/usr/bin/env python3
"""
Judo Club Article Generator

This script transforms judo club data from an Excel file into an NLP-friendly, 
semantically-rich article with website screenshots, and exports it as a markdown file.
"""

import os
import time
import re
import uuid
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
from io import BytesIO

# Excel file processing
import pandas as pd
import openpyxl

# Web browsing and screenshots
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager

# Image processing
from PIL import Image, ImageOps, ImageEnhance

# NLP and semantic processing
import spacy
import nltk
from nltk.tokenize import sent_tokenize
import rdflib
from rdflib import Graph, Literal, RDF, URIRef, Namespace
from rdflib.namespace import RDFS, XSD, FOAF, SKOS

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Download NLTK resources
nltk.download('punkt', quiet=True)

# Load spaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # Download the model if not available
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")


class JudoClubArticleGenerator:
    """
    Generates an NLP-friendly, semantically-rich article about judo clubs
    with website screenshots.
    """

    def __init__(self, excel_path: str = "attached_assets/Outscraper-20250228190440xs1c_judo_club__1.xlsx"):
        """
        Initialize the generator.
        
        Args:
            excel_path: Path to the Excel file containing judo club data
        """
        self.excel_path = excel_path
        
        # Configure driver
        self.driver = None
        
        # Define schema.org namespaces for semantic triples
        self.schema = Namespace("http://schema.org/")
        
        # Initialize RDF graph
        self.graph = Graph()
        self.graph.bind("schema", self.schema)
        self.graph.bind("foaf", FOAF)
        
        # Set up directories
        self.image_dir = "images"
        self.temp_dir = "temp"
        
        # Image quality settings
        self.image_quality = 85
        self.max_image_width = 800
        
        logger.info("JudoClubArticleGenerator initialized")
    
    def setup_browser(self) -> None:
        """Set up the browser for taking screenshots."""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Install the Chrome driver
        service = Service(ChromeDriverManager().install())
        
        self.driver = webdriver.Chrome(service=service, options=options)
        logger.info("Browser setup complete")
    
    def close_browser(self) -> None:
        """Close the browser."""
        if self.driver:
            self.driver.quit()
            logger.info("Browser closed")
    
    def fetch_excel_data(self) -> List[Dict[str, Any]]:
        """
        Fetch judo club data from Excel file.
            
        Returns:
            List of dictionaries containing judo club data with validated fields
        """
        logger.info(f"Fetching data from Excel file: {self.excel_path}")
        
        try:
            # Read Excel file
            df = pd.read_excel(self.excel_path)
            
            # Clean column names by stripping whitespace
            df.columns = df.columns.str.strip()
            
            # Filter out rows where name is missing or NaN
            df = df.dropna(subset=['name'])
            
            # Ensure phone numbers are strings, not floats
            if 'phone' in df.columns:
                df['phone'] = df['phone'].apply(lambda x: str(x) if isinstance(x, str) or not pd.isna(x) else '')
                # Remove "nan" strings that might have been created
                df['phone'] = df['phone'].apply(lambda x: '' if x.lower() == 'nan' else x)
            
            # Ensure websites are strings, not floats
            if 'site' in df.columns:
                df['site'] = df['site'].apply(lambda x: str(x) if isinstance(x, str) or not pd.isna(x) else '')
                # Remove "nan" strings that might have been created
                df['site'] = df['site'].apply(lambda x: '' if x.lower() == 'nan' else x)
                
            # Ensure addresses are strings, not floats
            if 'full_address' in df.columns:
                df['full_address'] = df['full_address'].apply(lambda x: str(x) if isinstance(x, str) or not pd.isna(x) else '')
                # Remove "nan" strings that might have been created
                df['full_address'] = df['full_address'].apply(lambda x: '' if x.lower() == 'nan' else x)
            
            # Convert DataFrame to list of dictionaries
            data = df.to_dict('records')
            
            logger.info(f"Retrieved {len(data)} judo clubs from Excel file")
            return data
        except Exception as e:
            logger.error(f"Failed to read Excel file: {str(e)}")
            return []
    
    def take_screenshot(self, url: str) -> Optional[Image.Image]:
        """
        Take a screenshot of a website.
        
        Args:
            url: Website URL
            
        Returns:
            PIL Image object or None if screenshot failed
        """
        if not url:
            return None
        
        # Ensure URL has protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            logger.info(f"Taking screenshot of {url}")
            self.driver.get(url)
            
            # Wait for page to load
            time.sleep(5)
            
            # Take screenshot
            screenshot = self.driver.get_screenshot_as_png()
            image = Image.open(BytesIO(screenshot))
            
            return image
        except (WebDriverException, TimeoutException) as e:
            logger.error(f"Failed to take screenshot of {url}: {str(e)}")
            return None
    
    def process_image(self, image: Image.Image, club_name: str) -> Tuple[Image.Image, str]:
        """
        Process and optimize the screenshot.
        
        Args:
            image: PIL Image object
            club_name: Name of the judo club
            
        Returns:
            Tuple of (processed image, filename)
        """
        # Resize image if needed
        if image.width > self.max_image_width:
            ratio = self.max_image_width / image.width
            new_height = int(image.height * ratio)
            image = image.resize((self.max_image_width, new_height), Image.LANCZOS)
        
        # Enhance image
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.2)
        
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.1)
        
        # Generate safe filename
        safe_name = re.sub(r'[^\w\s-]', '', club_name).strip().lower()
        safe_name = re.sub(r'[-\s]+', '-', safe_name)
        filename = f"{safe_name}-screenshot.jpg"
        
        logger.info(f"Processed image for {club_name}")
        return image, filename
    
    def generate_semantic_triples(self, club: Dict[str, Any]) -> None:
        """
        Generate semantic triples for a judo club and add them to the RDF graph.
        
        Args:
            club: Dictionary containing judo club data
        """
        # Create a unique identifier for this club
        club_id = str(uuid.uuid4())
        club_uri = URIRef(f"http://judonearme.com/club/{club_id}")
        
        # Add club type
        self.graph.add((club_uri, RDF.type, self.schema.SportsClub))
        self.graph.add((club_uri, self.schema.sportType, Literal("Judo")))
        
        # Add basic properties (using outscraper column names)
        name = club.get('name', '')
        if name:
            self.graph.add((club_uri, self.schema.name, Literal(name)))
        
        address = club.get('full_address', '')
        if address:
            self.graph.add((club_uri, self.schema.address, Literal(address)))
        
        phone = club.get('phone', '')
        if phone and isinstance(phone, str) and phone.strip():
            self.graph.add((club_uri, self.schema.telephone, Literal(phone)))
        
        website = club.get('site', '')
        if website and isinstance(website, str) and website.strip():
            self.graph.add((club_uri, self.schema.url, Literal(website)))
        
        rating = club.get('rating', '')
        if rating and isinstance(rating, (int, float)) and not pd.isna(rating):
            self.graph.add((club_uri, self.schema.aggregateRating, Literal(rating, datatype=XSD.decimal)))
        
        reviews = club.get('reviews', '')
        if reviews and isinstance(reviews, (int, float)) and not pd.isna(reviews):
            self.graph.add((club_uri, self.schema.reviewCount, Literal(int(reviews), datatype=XSD.integer)))
        
        # Add geo coordinates if available
        latitude = club.get('latitude', '')
        longitude = club.get('longitude', '')
        if (latitude and longitude and 
            isinstance(latitude, (int, float)) and not pd.isna(latitude) and
            isinstance(longitude, (int, float)) and not pd.isna(longitude)):
            geo_uri = URIRef(f"http://judonearme.com/geo/{club_id}")
            self.graph.add((geo_uri, RDF.type, self.schema.GeoCoordinates))
            self.graph.add((geo_uri, self.schema.latitude, Literal(latitude, datatype=XSD.decimal)))
            self.graph.add((geo_uri, self.schema.longitude, Literal(longitude, datatype=XSD.decimal)))
            self.graph.add((club_uri, self.schema.geo, geo_uri))
        
        logger.info(f"Generated semantic triples for {name}")
    
    def generate_schema_org_jsonld(self, clubs: List[Dict[str, Any]]) -> str:
        """
        Generate Schema.org JSON-LD for the article.
        
        Args:
            clubs: List of judo club data
            
        Returns:
            JSON-LD string
        """
        article_jsonld = {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "Judo Clubs in San Jose: A Comprehensive Guide",
            "author": {
                "@type": "Person",
                "name": "Judo Near Me"
            },
            "publisher": {
                "@type": "Organization",
                "name": "Judo Near Me",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://judonearme.com/logo.png"
                }
            },
            "datePublished": time.strftime("%Y-%m-%d"),
            "dateModified": time.strftime("%Y-%m-%d"),
            "mainEntityOfPage": {
                "@type": "WebPage",
                "@id": "https://judonearme.com/judo-san-jose"
            },
            "about": {
                "@type": "Thing",
                "name": "Judo",
                "description": "A modern Japanese martial art and Olympic sport"
            },
            "mentions": []
        }
        
        # Add each club as a mentioned entity
        for club in clubs:
            if "name" not in club or not club["name"]:
                continue
                
            club_entry = {
                "@type": "SportsClub",
                "name": club.get("name", ""),
                "sportType": "Judo"
            }
            
            if club.get("full_address"):
                club_entry["address"] = {
                    "@type": "PostalAddress",
                    "streetAddress": club.get("full_address", "")
                }
            
            if club.get("phone") and isinstance(club.get("phone"), str) and club.get("phone").strip():
                club_entry["telephone"] = club.get("phone", "")
                
            if club.get("site") and isinstance(club.get("site"), str) and club.get("site").strip():
                club_entry["url"] = club.get("site", "")
                
            rating = club.get("rating")
            reviews = club.get("reviews")
            
            if (rating and isinstance(rating, (int, float)) and not pd.isna(rating)):
                club_entry["aggregateRating"] = {
                    "@type": "AggregateRating",
                    "ratingValue": rating,
                    "reviewCount": int(reviews) if reviews and isinstance(reviews, (int, float)) and not pd.isna(reviews) else 0
                }
                
            # Add geo coordinates if available
            lat = club.get("latitude")
            lng = club.get("longitude")
            if (lat and lng and 
                isinstance(lat, (int, float)) and not pd.isna(lat) and
                isinstance(lng, (int, float)) and not pd.isna(lng)):
                club_entry["geo"] = {
                    "@type": "GeoCoordinates",
                    "latitude": lat,
                    "longitude": lng
                }
                
            article_jsonld["mentions"].append(club_entry)
        
        return json.dumps(article_jsonld, indent=2)
    
    def generate_nlp_optimized_description(self, club: Dict[str, Any]) -> str:
        """
        Generate a semantically rich, NLP-friendly description with high-salience entities,
        LSI keywords, and domain-specific terminology for a judo club.
        
        Args:
            club: Dictionary containing judo club data
            
        Returns:
            Search-optimized description with semantic richness
        """
        import random
        
        name = club.get('name', 'This judo club')
        address = club.get('full_address', 'the San Jose area')
        rating = club.get('rating', None)
        reviews = club.get('reviews', None)
        
        # Core martial arts vocabulary (high-salience domain entities)
        judo_terms = [
            "martial arts training center", "judo techniques academy", 
            "martial arts dojo", "judo instruction facility", "martial arts school",
            "traditional judo dojo", "competitive judo facility", "judo training center"
        ]
        
        # LSI keywords related to judo and martial arts training
        lsi_keywords = [
            "self-defense skills", "Olympic sport training", "Japanese martial art", 
            "throwing techniques", "ground fighting", "belt ranking system",
            "certified instructors", "tatami mats", "training methodology"
        ]
        
        # Randomly select terms to include for semantic variety and LSI optimization
        selected_judo_term = random.choice(judo_terms)
        selected_lsi_keyword1 = random.choice(lsi_keywords)
        selected_lsi_keyword2 = random.choice([k for k in lsi_keywords if k != selected_lsi_keyword1])
        
        # Enhanced semantically-rich base description with high-salience entities
        description = f"{name} is a premier {selected_judo_term} located in {address}. "
        
        # Add relevant rating information if available with semantic enhancement
        if rating and reviews:
            if (isinstance(rating, (int, float)) and not pd.isna(rating) and 
                isinstance(reviews, (int, float)) and not pd.isna(reviews)):
                
                description += f"With a rating of {rating} stars based on {int(reviews)} reviews, "
                
                if rating >= 4.5:
                    description += "it is highly regarded in the local martial arts community. "
                elif rating >= 4.0:
                    description += "it is well-respected in the local martial arts community. "
                elif rating >= 3.5:
                    description += "it has received positive feedback from the community. "
                else:
                    description += "it provides judo training services to the community. "
        
        # Add semantically-rich information about offerings with LSI keywords
        description += f"{name} offers comprehensive judo programs focused on {selected_lsi_keyword1} and {selected_lsi_keyword2} "
        description += f"for all skill levels, from beginners to advanced practitioners. "
        
        # Process with spaCy to ensure proper entity recognition
        doc = nlp(description)
        
        # Ensure proper location recognition
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        has_location = any(label == "GPE" or label == "LOC" for _, label in entities)
        
        if not has_location and "San Jose" not in description:
            description += "Located in the San Jose region, this facility is ideal for anyone interested in learning judo. "
            
        logger.info(f"Generated NLP-optimized description for {name}")
        return description
    
    def generate_markdown_article(self, clubs: List[Dict[str, Any]], screenshots: Dict[str, str]) -> str:
        """
        Generate a semantically-rich Markdown article.
        
        Args:
            clubs: List of judo club data
            screenshots: Dictionary mapping club names to screenshot filenames
            
        Returns:
            Markdown string
        """
        # Enhanced article structure with improved navigation and semantic HTML
        markdown = """<style>
/* Enhanced styling for the entire article */
body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  line-height: 1.6;
  color: #333;
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

/* Club rating styling */
.club-rating {
  margin: 10px 0;
}

.rating-display {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}

.stars {
  color: #FFD700 !important; /* Gold color for stars */
  font-size: 1.5em !important;
  margin-right: 10px;
  letter-spacing: 2px;
  text-shadow: 1px 1px 1px rgba(0,0,0,0.1);
}

.rating-text {
  font-size: 0.95em;
  color: #555;
}

/* Club section styling */
.club-section {
  background-color: #f9f9f9;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 5px rgba(0,0,0,0.1);
  transition: transform 0.2s;
}

.club-section:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.club-title {
  color: #1a5276;
  margin-top: 0;
  border-bottom: 2px solid #1a5276;
  padding-bottom: 10px;
}

/* Navigation controls */
.navigation-controls {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}

.back-to-top-link, .back-to-listings-link {
  background-color: #1a5276;
  color: white;
  padding: 8px 15px;
  border-radius: 4px;
  text-decoration: none;
  font-size: 0.9em;
  transition: background-color 0.2s;
}

.back-to-top-link:hover, .back-to-listings-link:hover {
  background-color: #154360;
}

/* Club info styling */
.club-info-list {
  list-style-type: none;
  padding: 0;
}

.club-info-list li {
  margin-bottom: 8px;
  padding-left: 20px;
  position: relative;
}

.club-info-list li::before {
  content: "•";
  color: #1a5276;
  font-weight: bold;
  position: absolute;
  left: 0;
}

/* Article navigation */
.article-nav {
  background-color: #1a5276;
  color: white;
  padding: 10px 0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.nav-container {
  display: flex;
  justify-content: center;
  gap: 20px;
}

.nav-item {
  color: white;
  text-decoration: none;
  padding: 5px 10px;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.nav-item:hover {
  background-color: rgba(255,255,255,0.2);
}

/* Responsive design */
@media (max-width: 768px) {
  .nav-container {
    flex-direction: column;
    align-items: center;
    gap: 10px;
  }
  
  .club-section {
    padding: 15px;
  }
}
</style>

<div id="top" class="article-top"></div>
<nav aria-label="Article Navigation" class="article-nav">
  <div class="nav-container">
    <a href="#introduction" class="nav-item">Introduction</a>
    <a href="#club-listings" class="nav-item">Judo Clubs</a>
    <a href="#conclusion" class="nav-item">Find a Club</a>
  </div>
</nav>

"""
        
        markdown += '<header class="article-header">\n'
        markdown += '  <h1 id="main-title">Judo Clubs in San Jose: A Comprehensive Guide</h1>\n'
        markdown += '  <p class="publication-date">Published: ' + time.strftime("%B %d, %Y") + '</p>\n'
        markdown += '</header>\n\n'
        
        # Add schema.org JSON-LD for enhanced search engine understanding
        markdown += "<script type=\"application/ld+json\">\n"
        markdown += self.generate_schema_org_jsonld(clubs)
        markdown += "\n</script>\n\n"
        
        # Introduction with rich semantic markup and enhanced content structure
        markdown += """
<section id="introduction" class="article-section introduction-section" itemscope itemtype="http://schema.org/Article">
  <meta itemprop="headline" content="Judo Clubs in San Jose: A Comprehensive Guide">

  <h2 class="section-title">Introduction to San Jose Judo Training</h2>

  <div itemprop="articleBody" class="article-content">
    <p class="lead-paragraph"><strong>Looking for judo training in San Jose?</strong> This comprehensive guide lists all verified judo clubs in the San Jose area with detailed information including addresses, phone numbers, websites, and community ratings.</p>

    <p>We've researched and compiled data on 14 judo training facilities throughout San Jose to help you find the perfect dojo based on:</p>
    <ul class="feature-list">
      <li><strong>Location:</strong> Find clubs closest to your neighborhood or workplace</li>
      <li><strong>Ratings:</strong> See which clubs have the highest community ratings and reviews</li>
      <li><strong>Contact info:</strong> Access direct phone numbers and websites for immediate information</li>
      <li><strong>Training focus:</strong> Identify clubs specializing in competitive, traditional, or recreational judo</li>
    </ul>

    <p>Use our enhanced navigation system to quickly jump to specific judo clubs or browse the complete listings below. Each club entry includes NLP-optimized descriptions highlighting their unique offerings and benefits.</p>
    
    <div class="navigation-hint">
      <p><em>Tip: Use the quick navigation links below or the menu at the top to easily move between sections. Each club listing includes a "Back to top" link for convenient browsing.</em></p>
    </div>
  </div>
</section>

<h2 id="club-listings" class="section-title">San Jose Area Judo Clubs</h2>

"""
        
        # Enhanced quick navigation with semantic markup and structured data
        markdown += '<nav aria-label="Club Navigation" class="club-navigation">\n'
        markdown += '  <div class="nav-container">\n'
        markdown += '    <h3 class="nav-title">Quick Club Navigation</h3>\n'
        markdown += '    <ul class="club-nav-list">\n'
        markdown += '      <li class="nav-item"><a href="#introduction" class="nav-link">Introduction</a></li>\n'
        
        # Generate club navigation entries with improved formatting
        for i, club in enumerate(clubs, 1):
            name = club.get('name', '')
            if not name:
                continue
            club_id = name.lower().replace(" ", "-").replace("'", "").replace("&", "and")
            markdown += f'      <li class="nav-item"><a href="#{club_id}" class="nav-link">{i}. {name}</a></li>\n'
        
        markdown += '      <li class="nav-item"><a href="#conclusion" class="nav-link">Finding Your Club</a></li>\n'
        markdown += '    </ul>\n'
        markdown += '  </div>\n'
        markdown += '</nav>\n\n'
        
        # Generate content for each club with enhanced semantic HTML
        for i, club in enumerate(clubs, 1):
            name = club.get('name', '')
            if not name:
                continue
                
            address = club.get('full_address', '')
            phone = club.get('phone', '')
            website = club.get('site', '')
            
            # Create more robust ID for club anchors - replace spaces, special chars, etc.
            club_id = name.lower().replace(" ", "-").replace("'", "").replace("&", "and").replace(".", "")
            club_id = ''.join(c for c in club_id if c.isalnum() or c == '-')
            
            # Create club section with enhanced semantic markup and structured data
            markdown += f'<section class="club-section" itemscope itemtype="http://schema.org/SportsClub" id="{club_id}">\n'
            markdown += f'<h3 class="club-title" itemprop="name">{i}. {name}</h3>\n\n'
            
            # Add ratings snippet with structured data if available
            rating = club.get('rating', '')
            review_count = club.get('reviews', '')  # Updated to use 'reviews' column
            
            # Debug log to check rating data types
            logger.info(f"Club: {name}, Rating: {rating} (type: {type(rating)}), Review count: {review_count} (type: {type(review_count)})")
            
            # Fix rating if it's a string
            if isinstance(rating, str) and rating.strip():
                try:
                    rating = float(rating.replace(',', '.'))
                except ValueError:
                    rating = 0
            
            # Fix review count if it's a string
            if isinstance(review_count, str) and review_count.strip():
                try:
                    review_count = int(review_count.replace(',', ''))
                except ValueError:
                    review_count = 0
            
            # Use the correct fields to check if we have valid rating data
            if (rating and isinstance(rating, (int, float)) and not pd.isna(rating) and 
                review_count and isinstance(review_count, (int, float)) and not pd.isna(review_count)):
                
                markdown += '<div class="club-rating" itemprop="aggregateRating" itemscope itemtype="http://schema.org/AggregateRating">\n'
                markdown += f'  <meta itemprop="ratingValue" content="{rating}">\n'
                markdown += f'  <meta itemprop="reviewCount" content="{int(review_count)}">\n'
                
                # Improved visual rating display with half-stars
                full_stars = int(rating)
                half_star = (rating - full_stars) >= 0.3 and (rating - full_stars) < 0.8
                quarter_star = (rating - full_stars) > 0 and (rating - full_stars) < 0.3
                three_quarter_star = (rating - full_stars) >= 0.8
                
                # Calculate how many of each type of star to display
                stars = '★' * full_stars
                
                if half_star:
                    stars += '½'
                elif quarter_star:
                    stars += '¼'
                elif three_quarter_star:
                    stars += '¾'
                    
                # Add empty stars to fill the 5-star scale
                remaining_empty = 5 - full_stars - (1 if half_star or quarter_star or three_quarter_star else 0)
                stars += '☆' * remaining_empty
                
                # Create the CSS for the stars display with proper color
                star_styles = 'color: #FFD700; font-size: 1.2em;'
                
                markdown += f'  <div class="rating-display">\n'
                markdown += f'    <span class="stars" style="{star_styles}" aria-label="{rating} out of 5 stars">{stars}</span>\n'
                markdown += f'    <span class="rating-text">{rating} out of 5 ({int(review_count)} reviews)</span>\n'
                markdown += f'  </div>\n'
                markdown += '</div>\n\n'
            
            # Add screenshot if available with improved image markup and structured data
            if name in screenshots:
                screenshot_path = f"images/{screenshots[name]}"
                markdown += f'<div class="club-image-container">\n'
                markdown += f'  <figure itemprop="image" itemscope itemtype="http://schema.org/ImageObject">\n'
                markdown += f'    <meta itemprop="contentUrl" content="{screenshot_path}">\n'
                markdown += f'    <meta itemprop="name" content="{name} website screenshot">\n'
                markdown += f'    <img src="{screenshot_path}" alt="Screenshot of {name} website" width="800" height="auto" loading="lazy">\n'
                markdown += f'    <figcaption class="image-caption">Website screenshot of <span itemprop="caption">{name}</span>, a judo training facility in San Jose area</figcaption>\n'
                markdown += f'  </figure>\n'
                markdown += f'</div>\n\n'
            
            # Get geo coordinates if available
            latitude = club.get('latitude', '')
            longitude = club.get('longitude', '')
            
            # Include geo data if available
            if (latitude and longitude and 
                isinstance(latitude, (int, float)) and not pd.isna(latitude) and
                isinstance(longitude, (int, float)) and not pd.isna(longitude)):
                
                markdown += f'<div class="hidden-geo-data">\n'
                markdown += f'  <meta itemprop="geo" itemscope itemtype="http://schema.org/GeoCoordinates">\n'
                markdown += f'  <meta itemprop="latitude" content="{latitude}">\n'
                markdown += f'  <meta itemprop="longitude" content="{longitude}">\n'
                markdown += f'</div>\n\n'
            
            # NLP-optimized description with better semantic structure
            markdown += '<div class="club-description-container">\n'
            markdown += '  <div class="club-description" itemprop="description">\n'
            markdown += self.generate_nlp_optimized_description(club)
            markdown += '\n  </div>\n'
            markdown += '</div>\n\n'
            
            # Enhanced contact information with improved semantics
            markdown += '<div class="club-info-container">\n'
            markdown += '  <h4 class="info-title">Club Information:</h4>\n'
            markdown += '  <ul class="club-info-list">\n'
            
            if address:
                markdown += f'    <li class="address-item"><strong>Address:</strong> <span itemprop="address" itemscope itemtype="http://schema.org/PostalAddress"><span itemprop="streetAddress">{address}</span></span></li>\n'
            
            if phone and isinstance(phone, str) and phone.strip():
                clean_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
                markdown += f'    <li class="phone-item"><strong>Phone:</strong> <a href="tel:{clean_phone}" itemprop="telephone">{phone}</a></li>\n'
            
            if website and isinstance(website, str) and website.strip():  # Only add website if it exists and is not empty
                markdown += f'    <li class="website-item"><strong>Website:</strong> <a href="{website}" itemprop="url" target="_blank" rel="noopener noreferrer">{website}</a></li>\n'
            
            # Add club type and features if known
            markdown += f'    <li class="category-item"><strong>Category:</strong> <span itemprop="knowsAbout">Judo Training</span></li>\n'
            
            # Add hours of operation if available
            hours = club.get('hours', '')
            if hours and isinstance(hours, str) and hours.strip():
                markdown += f'    <li class="hours-item"><strong>Hours:</strong> <time itemprop="openingHours">{hours}</time></li>\n'
            
            markdown += '  </ul>\n'
            markdown += '</div>\n'
            
            # Return to top navigation with improved design
            markdown += f'<div class="navigation-controls">\n'
            markdown += f'  <a href="#top" class="back-to-top-link" aria-label="Back to top of page">↑ Back to top</a>\n'
            markdown += f'  <a href="#club-listings" class="back-to-listings-link" aria-label="Back to club listings">← All clubs</a>\n'
            markdown += f'</div>\n'
            
            markdown += '</section>\n\n'
            
            if i < len(clubs):
                markdown += '<hr class="club-separator" />\n\n'
        
        # Get the current date
        current_date = time.strftime("%B %d, %Y")
        
        # Enhanced conclusion with improved semantic structure and call-to-action
        markdown += f"""
<section id="conclusion" class="conclusion-section" itemscope itemtype="http://schema.org/Article">
  <h2 class="section-title">Find Your San Jose Judo Club Today</h2>
  
  <div class="article-content" itemprop="articleBody">
    <div class="call-to-action-container">
      <p class="cta-intro">Ready to start your judo journey in San Jose? Here's what to do next:</p>
  
      <ol class="action-steps">
        <li class="action-step">
          <h3 class="step-title"><span class="step-number">1</span> Choose a club</h3>
          <p class="step-description">Select from the 14 verified locations above based on location, ratings, and specific training offerings that match your needs.</p>
        </li>
        
        <li class="action-step">
          <h3 class="step-title"><span class="step-number">2</span> Contact directly</h3>
          <p class="step-description">Call the phone number or visit the website to confirm current class schedules, pricing, and any special requirements.</p>
        </li>
        
        <li class="action-step">
          <h3 class="step-title"><span class="step-number">3</span> Visit in person</h3>
          <p class="step-description">Most clubs offer a free trial class or observation period to help you determine if the environment and teaching style are right for you.</p>
        </li>
      </ol>
    </div>
    
    <div class="community-information">
      <h3 class="subsection-title">San Jose Judo Community</h3>
      <p>San Jose's judo community welcomes practitioners of all levels, from complete beginners to advanced competitors. Many clubs offer specialized programs for:</p>
      
      <ul class="program-list">
        <li><span class="program-category">Age groups:</span> Children (4-12), teens (13-17), and adults</li>
        <li><span class="program-category">Experience levels:</span> Beginner, intermediate, and advanced classes</li>
        <li><span class="program-category">Training goals:</span> Recreational practice, competitive preparation, or self-defense</li>
      </ul>
      
      <p>With flexible scheduling options including evening and weekend classes, finding a program that fits your lifestyle is achievable.</p>
    </div>
    
    <div class="guide-information">
      <p class="update-note"><em>This comprehensive guide to San Jose judo clubs is updated regularly to ensure accurate information about judo training facilities in the San Jose area. Last content verification: {current_date}.</em></p>
      
      <div class="back-to-navigation">
        <a href="#top" class="nav-link">↑ Back to top</a> | 
        <a href="#club-listings" class="nav-link">↑ Back to club listings</a>
      </div>
    </div>
  </div>
</section>

<footer class="article-footer">
  <div class="footer-content">
    <p class="update-date">Last updated: {current_date}</p>
    <p class="copyright-notice">© {time.strftime("%Y")} Judo Club Directory</p>
  </div>
</footer>
"""
        
        logger.info("Generated Markdown article")
        return markdown
    
    def save_to_local(self, markdown_content: str, images: Dict[str, Image.Image]) -> None:
        """
        Save the article and images to local directories.
        
        Args:
            markdown_content: Markdown article content
            images: Dictionary mapping filenames to PIL Image objects
        """
        try:
            logger.info("Saving content to local directories")
            
            # Ensure the images directory exists
            os.makedirs(self.image_dir, exist_ok=True)
            
            # Ensure the usa directory exists for country-specific content
            os.makedirs("usa", exist_ok=True)
            
            # Save each image to the images directory
            for filename, image in images.items():
                image_path = os.path.join(self.image_dir, filename)
                image.save(image_path, format='JPEG', quality=self.image_quality)
                logger.info(f"Saved image: {image_path}")
            
            # Save the markdown file to the usa folder with dash-separated filename
            markdown_path = os.path.join("usa", "judo-clubs-san-jose.md")
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info(f"Successfully saved markdown article to {markdown_path}")
        except Exception as e:
            logger.error(f"Failed to save content locally: {str(e)}")
            raise
    
    def run(self, skip_screenshots=True) -> None:
        """Run the entire pipeline to generate and publish the article.
        
        Args:
            skip_screenshots: If True, skip taking website screenshots (useful when running in environments without Chrome)
        """
        try:
            # Fetch data
            clubs = self.fetch_excel_data()
            
            if not clubs:
                logger.error("No judo club data found. Exiting.")
                return
            
            # Process each club
            screenshots = {}  # Map club names to screenshot filenames
            processed_images = {}  # Map filenames to PIL images
            
            if not skip_screenshots:
                # Set up browser for screenshots
                self.setup_browser()
                
                # Take screenshots for each club
                for club in clubs:
                    name = club.get('name', '')
                    website = club.get('site', '')
                    
                    if name and website and website.strip():
                        # Take screenshot only if website exists and is not empty
                        screenshot = self.take_screenshot(website)
                        
                        if screenshot:
                            # Process image
                            processed_image, filename = self.process_image(screenshot, name)
                            screenshots[name] = filename
                            processed_images[filename] = processed_image
            
            # Generate semantic triples
            for club in clubs:
                self.generate_semantic_triples(club)
            
            # Generate Markdown article
            markdown_content = self.generate_markdown_article(clubs, screenshots)
            
            # Save markdown file (and images if any)
            if not skip_screenshots:
                self.save_to_local(markdown_content, processed_images)
            else:
                # Save just the markdown file without images
                try:
                    # Ensure the usa directory exists
                    os.makedirs("usa", exist_ok=True)
                    
                    # Save to the usa folder
                    markdown_path = os.path.join("usa", "judo-clubs-san-jose.md")
                    with open(markdown_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    logger.info(f"Successfully saved markdown article to {markdown_path}")
                except Exception as e:
                    logger.error(f"Failed to save markdown file: {str(e)}")
                    raise
            
            logger.info("Article generation complete")
            
        except Exception as e:
            logger.error(f"Error in article generation pipeline: {str(e)}")
            raise
        finally:
            # Clean up
            if not skip_screenshots:
                self.close_browser()


if __name__ == "__main__":
    # Initialize and run the generator
    generator = JudoClubArticleGenerator()
    generator.run()