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
            List of dictionaries containing judo club data
        """
        logger.info(f"Fetching data from Excel file: {self.excel_path}")
        
        try:
            # Read Excel file
            df = pd.read_excel(self.excel_path)
            
            # Clean column names by stripping whitespace
            df.columns = df.columns.str.strip()
            
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
        if phone:
            self.graph.add((club_uri, self.schema.telephone, Literal(phone)))
        
        website = club.get('site', '')
        if website:
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
            
            if club.get("phone"):
                club_entry["telephone"] = club.get("phone", "")
                
            if club.get("site"):
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
        Generate an NLP-optimized description for a judo club.
        
        Args:
            club: Dictionary containing judo club data
            
        Returns:
            NLP-optimized description string
        """
        name = club.get('name', 'This judo club')
        address = club.get('full_address', 'the San Jose area')
        rating = club.get('rating', None)
        reviews = club.get('reviews', None)
        
        # Base description
        description = f"{name} is a judo training facility located in {address}. "
        
        # Add rating information if available
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
        
        # Add semantic NLP-friendly content about judo benefits
        description += f"At {name}, students can learn the traditional Japanese martial art of judo, which focuses on throws, takedowns, and grappling techniques. "
        description += "Judo practice offers numerous benefits including improved physical fitness, mental discipline, stress reduction, and self-defense skills. "
        description += f"The club welcomes practitioners of all skill levels, from beginners to advanced judoka, providing a supportive environment to develop martial arts proficiency. "
        
        # Process with spaCy to ensure NLP-friendliness
        doc = nlp(description)
        
        # Ensure proper noun recognition and entity linking
        entities = [(ent.text, ent.label_) for ent in doc.ents]
        has_location = any(label == "GPE" or label == "LOC" for _, label in entities)
        
        if not has_location and "San Jose" not in description:
            description += "This dojo contributes to the rich martial arts culture of the San Jose region. "
            
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
        # Article title and introduction
        markdown = "# Judo Clubs in San Jose: A Comprehensive Guide\n\n"
        
        # Add schema.org JSON-LD
        markdown += "<script type=\"application/ld+json\">\n"
        markdown += self.generate_schema_org_jsonld(clubs)
        markdown += "\n</script>\n\n"
        
        # Introduction with semantic triples
        markdown += """
<section itemscope itemtype="http://schema.org/Article">
<meta itemprop="headline" content="Judo Clubs in San Jose: A Comprehensive Guide">

## Introduction

<div itemprop="articleBody">
<p>Judo, an Olympic sport and martial art founded by Jigoro Kano in 1882, offers practitioners a powerful combination of physical conditioning, mental discipline, and practical self-defense skills. The San Jose area boasts several high-quality judo clubs where individuals of all ages and skill levels can learn and practice this traditional Japanese martial art.</p>

<p>This comprehensive guide explores the top judo clubs in the San Jose region, providing essential information about each facility including location, contact details, and unique features. Whether you're a beginner looking to start your judo journey or an experienced judoka seeking a new dojo, this guide will help you find the perfect training environment to develop your skills on the mat.</p>
</div>
</section>

## San Jose Area Judo Clubs

"""
        
        # Generate content for each club
        for i, club in enumerate(clubs, 1):
            name = club.get('name', '')
            if not name:
                continue
                
            address = club.get('full_address', '')
            phone = club.get('phone', '')
            website = club.get('site', '')
            
            # Create club section with semantic markup
            markdown += f'<section itemscope itemtype="http://schema.org/SportsClub" id="{name.lower().replace(" ", "-")}">\n'
            markdown += f'<h3 itemprop="name">{i}. {name}</h3>\n\n'
            
            # Add screenshot if available
            if name in screenshots:
                screenshot_path = f"images/{screenshots[name]}"
                markdown += f'<div class="club-image">\n'
                markdown += f'  <img src="{screenshot_path}" alt="Screenshot of {name} website" itemprop="image" width="800" loading="lazy">\n'
                markdown += f'  <p class="image-caption">Website screenshot of <span itemprop="name">{name}</span>, a judo training facility in San Jose area</p>\n'
                markdown += f'</div>\n\n'
            
            # NLP-optimized description
            markdown += '<div class="club-description" itemprop="description">\n'
            markdown += self.generate_nlp_optimized_description(club)
            markdown += '\n</div>\n\n'
            
            # Contact information
            markdown += '<div class="club-info">\n'
            markdown += '  <h4>Club Information:</h4>\n'
            markdown += '  <ul>\n'
            
            if address:
                markdown += f'    <li itemprop="address">{address}</li>\n'
            
            if phone:
                markdown += f'    <li>Phone: <span itemprop="telephone">{phone}</span></li>\n'
            
            if website:
                markdown += f'    <li>Website: <a href="{website}" itemprop="url" target="_blank" rel="noopener noreferrer">{website}</a></li>\n'
            
            markdown += '  </ul>\n'
            markdown += '</div>\n'
            
            markdown += '</section>\n\n'
            
            if i < len(clubs):
                markdown += '---\n\n'
        
        # Get the current date
        current_date = time.strftime("%B %d, %Y")
        
        # Conclusion
        markdown += f"""
## Benefits of Practicing Judo

<section>
<p>Judo offers numerous physical and mental benefits for practitioners of all ages:</p>

<ul>
  <li><strong>Physical fitness:</strong> Judo develops strength, flexibility, endurance, and coordination</li>
  <li><strong>Self-defense skills:</strong> Practical techniques that can be applied in real-world situations</li>
  <li><strong>Mental discipline:</strong> Improved focus, concentration, and decision-making abilities</li>
  <li><strong>Stress reduction:</strong> Physical activity combined with mindfulness techniques</li>
  <li><strong>Community connection:</strong> Belonging to a supportive group with shared interests</li>
</ul>

<p>Whether you're looking for physical exercise, mental challenge, or a new community, the judo clubs in San Jose offer excellent opportunities to experience the benefits of this traditional martial art.</p>
</section>

<footer>
<p>Last updated: {current_date}</p>
<p>Generated with NLP-enhanced semantic markup for optimal search engine visibility and accessibility.</p>
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
            
            # Save each image to the images directory
            for filename, image in images.items():
                image_path = os.path.join(self.image_dir, filename)
                image.save(image_path, format='JPEG', quality=self.image_quality)
                logger.info(f"Saved image: {image_path}")
            
            # Save the markdown file
            with open("judo_clubs_san_jose.md", 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            
            logger.info("Successfully saved content to local directories")
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
                    
                    if name and website:
                        # Take screenshot
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
                    with open("judo_clubs_san_jose.md", 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    logger.info("Successfully saved markdown article")
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