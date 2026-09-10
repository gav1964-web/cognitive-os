def index_pages(pages):
    index = []
    for page_number, page in enumerate(pages):
        for token in page:
            index.append({"page": page_number, "token": token})
    return index
