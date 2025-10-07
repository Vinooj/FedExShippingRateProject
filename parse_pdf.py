import os
import base64
import io
import openai
from pdf2image import convert_from_path
from pypdf import PdfReader # Import PdfReader to get total pages

# --- Configuration ---
# IMPORTANT: Set your OpenAI API key.
# It is highly recommended to set it as an environment variable for security.
# Example:
# In your terminal, run:
# export OPENAI_API_KEY='your_super_secret_api_key'
#
# If you are not using environment variables, you can uncomment the following line
# and replace "YOUR_OPENAI_API_KEY" with your actual key.
# os.environ['OPENAI_API_KEY'] = "YOUR_OPENAI_API_KEY"

# Initialize the OpenAI client
# The client will automatically look for the OPENAI_API_KEY environment variable.
try:
    client = openai.OpenAI()
    if not client.api_key:
        raise ValueError("OpenAI API key not found.")
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    print("Please make sure the OpenAI library is installed (`pip install openai`) and your API key is set.")
    exit()


PDF_FILE_PATH = "Service_Guide_2025_p13-15.pdf"
OUTPUT_CSV_PATH = "output.csv"
# PAGES_TO_PARSE is no longer a fixed tuple, it will be determined dynamically
# PAGES_TO_PARSE = (13, 14, 15)  # Page numbers are 1-based

def get_pdf_page_count(file_path):
    """Gets the total number of pages in a PDF file."""
    try:
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            return len(reader.pages)
    except Exception as e:
        print(f"Error getting PDF page count: {e}")
        return 0

def pdf_pages_to_base64_images(file_path, start_page, end_page):
    """Converts specified pages of a PDF to a list of base64 encoded images."""
    print(f"Converting PDF pages {start_page}-{end_page} to images. This may take a moment...")
    try:
        images = convert_from_path(file_path, first_page=start_page, last_page=end_page)
    except Exception as e:
        print(f"Error during PDF conversion: {e}")
        print("\n---")
        print("This script requires 'poppler' to be installed on your system.")
        print("On macOS, you can install it with Homebrew: `brew install poppler`")
        print("On Debian/Ubuntu, use: `sudo apt-get install poppler-utils`")
        print("---")
        return None

    base64_images = []
    for image in images:
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
        base64_images.append(base64_image)
    print(f"Successfully converted {len(base64_images)} pages to images.")
    return base64_images


def parse_tables_with_openai(base64_images):
    """Uses OpenAI's GPT-4 Vision model to extract tabular data from images."""
    print("Sending images to OpenAI for analysis. This can take some time...")
    
    # Constructing the prompt for the vision model
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "You are a raw tabular transcription engine. Convert the shipping-rate tables shown across ALL provided images into ONE continuous CSV. Do not interpret or summarize—transcribe every visible cell.\n"
                        "\n"
                        "Output rules (mandatory):\n"
                        "1) Return ONLY raw CSV text. No markdown, no prose, no code fences.\n"
                        "2) Produce exactly 152 lines total: 1 header + 151 data rows. Order:\n"
                        "   • Header (7 columns, exact): \"Service lbs,Next day by 8:30 a.m. — FedEx First Overnight,Next day by 10:30 a.m. — FedEx Priority Overnight,Next day by 3 p.m. — FedEx Standard Overnight,2-day by 10:30 a.m. — FedEx 2Day AM,2-day by 5 p.m. — FedEx 2Day,3-day by 5 p.m. — FedEx Express Saver\"\n"
                        "   • Row 2 label exactly: \"FedEx® Envelope up to 8 oz.\"\n"
                        "   • Rows 3–153 labels: 1,2,3,…,150 (one per lb).\n"
                        "3) Every row must have exactly 7 comma-separated fields; no blank rows.\n"
                        "4) If a price is unreadable, write \"NA\". Never omit a cell or row.\n"
                        "5) Never use ellipses (\"...\") or ranges. Every weight must appear explicitly.\n"
                        "6) Numbers: remove currency symbols and commas; keep two decimals (e.g., 73.31). Trim whitespace. No extra spaces around commas.\n"
                        "7) Treat images as one continuous table; ignore page headers/footers/notes.\n"
                        "8) If a weight is printed on one line and prices on the next, merge into a single CSV row for that weight.\n"
                        "9) If a weight appears twice, keep the most complete row (more non-NA cells).\n"
                        "10) Do not invent values.\n"
                        "\n"
                        "Validation (you must self-check before responding):\n"
                        "• Total lines = 152.\n"
                        "• First data row label exactly \"FedEx® Envelope up to 8 oz.\".\n"
                        "• Last data row label \"150\".\n"
                        "• 7 columns on every row.\n"
                        "• No markdown or commentary.\n"
                        "\n"
                        "Return ONLY the CSV text that satisfies these rules."
                    )
                },
                *[
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img}"
                        }
                    } for img in base64_images
                ]
            ]
        }
    ]

    try:
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=messages,
            max_tokens=4096,
        )
        return response.choices[0].message.content
    except openai.APIError as e:
        print(f"An error occurred with the OpenAI API: {e}")
        # You can add more specific error handling here if needed
        # For example, for authentication errors:
        if "authentication" in str(e).lower():
            print("\n---")
            print("Authentication error: Please check if your OpenAI API key is correct and has sufficient credits.")
            print("---")
    except Exception as e:
        print(f"An unexpected error occurred while calling the OpenAI API: {e}")
    
    return None

def main():
    """Main function to orchestrate the PDF parsing and CSV generation."""
    if not os.path.exists(PDF_FILE_PATH):
        print(f"Error: PDF file not found at '{PDF_FILE_PATH}'")
        return

    total_pages = get_pdf_page_count(PDF_FILE_PATH)
    if total_pages == 0:
        print("Could not determine the number of pages in the PDF. Exiting.")
        return

    print(f"Total pages in PDF: {total_pages}")
    
    # Process all pages
    base64_images = pdf_pages_to_base64_images(PDF_FILE_PATH, 1, total_pages)
    
    if not base64_images:
        return # Stop if PDF to image conversion failed

    csv_data = parse_tables_with_openai(base64_images)

    if csv_data:
        # The model might return the CSV data enclosed in markdown code blocks (```csv ... ```).
        # This part of the script cleans that up.
        if csv_data.startswith("```csv"):
            csv_data = csv_data[5:]
        if csv_data.endswith("```"):
            csv_data = csv_data[:-3]
        
        csv_data = csv_data.strip()

        try:
            with open(OUTPUT_CSV_PATH, "w", newline="", encoding='utf-8') as f:
                f.write(csv_data)
            print(f"\nSuccessfully saved extracted data to '{OUTPUT_CSV_PATH}'")
        except IOError as e:
            print(f"Error writing to file '{OUTPUT_CSV_PATH}': {e}")
    else:
        print("\nFailed to extract data using the OpenAI API. No output file was created.")

if __name__ == "__main__":
    main()