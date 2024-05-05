import os
import asyncio
import json
import pandas as pd
import tempfile
import uuid
from starlette.requests import Request
from fastapi import FastAPI, File, UploadFile, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from celery_worker import scrape_website
from sse_starlette.sse import EventSourceResponse

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Define a directory to store temporary files
TEMP_DIR = "temp_results"
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Initialize the results, urls, and keywords lists
results = []
urls = []
keywords = []

@app.get("/", response_class=HTMLResponse)
def read_form(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # Save the uploaded file
    with open("uploaded_file.xlsx", "wb") as buffer:
        buffer.write(await file.read())

    # Process the uploaded file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        with open("uploaded_file.xlsx", "rb") as file:
            tmp.write(file.read())
        tmp.flush()
        df = pd.read_excel(tmp.name)

    global results, urls, keywords
    results = []
    urls = []
    keywords = []
    for _, row in df.iterrows():
        url = row['URL']
        keyword = row['Keyword']
        result = scrape_website.delay(url, keyword)
        results.append(result)
        urls.append(url)
        keywords.append(keyword)

    return {"message": "File uploaded and processing started"}

@app.get("/scrape")
async def scrape_endpoint():
    async def event_generator():
        global urls, keywords
        # Check if any tasks have been started
        if not results:
            # If no tasks started, yield a ping event to keep connection alive
            yield "event: ping\ndata: null\n\n".encode()
            return

        while True:
            # Check if there are any scraping results available
            if results:
                # Send each scraping result as a separate server-sent event
                result = results.pop(0)
                url = urls.pop(0)
                keyword = keywords.pop(0)
                h1_count, h2_count, body_count = result.get()
                event_data = {
                    'url': url,
                    'keyword': keyword,
                    'h1_count': h1_count,
                    'h2_count': h2_count,
                    'body_count': body_count
                }

                # Generate a unique filename for the temporary file
                temp_file_name = f"{uuid.uuid4()}.csv"
                temp_file_path = os.path.join(TEMP_DIR, temp_file_name)
                with open(temp_file_path, "w") as temp_file:
                    temp_file.write(f"{url},{keyword},{h1_count},{h2_count},{body_count}\n")

                event_str = f"event: result\ndata: {json.dumps(event_data)}\n\n"
                yield event_str.encode()
            else:
                # If no results are available, check if all tasks are completed
                if all(result.ready() for result in results):
                    # If all tasks are completed, send the "complete" event
                    complete_event = "event: complete\ndata: null\n\n"
                    yield complete_event.encode()
                    break
                else:
                    # If tasks are still running, send a ping event to keep the connection alive
                    ping_event = "event: ping\ndata: null\n\n"
                    yield ping_event.encode()

            # Wait for a short interval before checking for results again
            await asyncio.sleep(1)

    return EventSourceResponse(event_generator())

@app.get("/download")
async def download_results():
    # Check if results exist
    if not os.path.exists(TEMP_DIR):
        return Response(content="No results available", media_type="text/plain")

    # Generate a CSV file with the scraped data
    csv_data = "URL,Keyword,H1 Count,H2 Count,Body Count\n"
    for file_name in os.listdir(TEMP_DIR):
        with open(os.path.join(TEMP_DIR, file_name), "r") as file:
            csv_data += file.read()

    # Return the CSV file as a response
    response = Response(content=csv_data, media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=results.csv"
    return response

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
