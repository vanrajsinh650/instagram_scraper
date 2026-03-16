import os
import logging
from scraper import InstagramScraper
from excel import save_to_excel
from utils import ensure_output_dir
from config import OUTPUT_DIR, OUTPUT_FILE

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Instagram Cafe Scraper pipeline...")
    
    try:
        # Create output directory if it doesn't exist
        ensure_output_dir()
        
        # Initialize and run scraper
        scraper = InstagramScraper()
        results = scraper.run()
        
        # Save results
        filepath = os.path.join(OUTPUT_DIR, OUTPUT_FILE)
        save_to_excel(results, filepath)
        
        logger.info("Pipeline completed successfully.")
        
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user. Exiting gracefully.")
    except Exception as e:
        logger.exception("Pipeline failed with unexpected error: %s", e)

if __name__ == "__main__":
    main()
