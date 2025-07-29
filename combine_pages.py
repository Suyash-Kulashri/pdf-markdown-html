from bs4 import BeautifulSoup

# Define the names of your HTML files
file_main = 'first_page_html.html'
file_to_append = 'remaining_pages.html'
file_output = 'combined_page.html'

try:
    # --- Read and parse both files ---
    with open(file_main, 'r', encoding='utf-8') as f:
        soup_main = BeautifulSoup(f, 'html.parser')

    with open(file_to_append, 'r', encoding='utf-8') as f:
        soup_append = BeautifulSoup(f, 'html.parser')

    # --- Find the head and body of the main file ---
    main_head = soup_main.head
    main_body = soup_main.body
    if not main_head or not main_body:
        raise TypeError("The main HTML file is missing a <head> or <body> tag.")

    # --- 1. Merge CSS from <head> ---
    if soup_append.head:
        # Find all <style> and <link rel="stylesheet"> tags in the second file
        styles_to_append = soup_append.head.find_all(['style', 'link'])
        
        for tag in styles_to_append:
            # Append only actual stylesheets, not other links like favicons
            if tag.name == 'link' and 'stylesheet' not in tag.get('rel', []):
                continue
            main_head.append(tag)
            print(f"Appended tag from head: {tag.name}")

    # --- 2. Merge content from <body> ---
    if soup_append.body:
        # Get all contents from the second file's body
        body_contents_to_append = soup_append.body.contents
        for element in body_contents_to_append:
            main_body.append(element)

    # --- Write the final combined HTML ---
    with open(file_output, 'w', encoding='utf-8') as f:
        f.write(str(soup_main.prettify()))

    print(f"\n✅ Successfully merged styles and content into '{file_output}'")

except FileNotFoundError as e:
    print(f"❌ Error: File not found - {e.filename}")
except Exception as e:
    print(f"An error occurred: {e}")