from flask import Flask, request, render_template, send_from_directory,flash,redirect,url_for
import os
import csv
import re
from io import BytesIO
import mammoth #for docx files
from azure_upload import get_blob_folders, get_blob_service_client, upload_folder_to_blob #functions fetched from azure_upload.py
from pdfminer.high_level import extract_text #extracting text chunks from pdf files
import spacy  #for nlp (extracting names and skills)
from spacy.matcher import Matcher #comparing patterns found with grammatical context
from dotenv import load_dotenv
load_dotenv()
app = Flask(__name__)

# Set the secret key
app.config['SECRET_KEY'] = 'rove2001'  
nlp = spacy.load('en_core_web_sm') #loading all the english words in variable nlp


AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
AZURE_CONTAINER_NAME = os.environ.get('AZURE_CONTAINER_NAME')  #put this in .env file
blob_service_client = get_blob_service_client(AZURE_STORAGE_CONNECTION_STRING)

@app.route('/')  #homepage of the webapp 
#rendering the form.html for frontend start
def form():  
    blob_service_client = get_blob_service_client(AZURE_STORAGE_CONNECTION_STRING)

    folders = get_blob_folders(blob_service_client, AZURE_CONTAINER_NAME)
    return render_template('form.html', folders=folders) 
#rendering the form.html for frontend finish

@app.route('/upload', methods=['POST'])
def upload():
    if 'resume-folder' not in request.files: #check if any resumes found in the selected folder for uploadation
        flash('No file part', 'error')
        return 'No file part'

    resume_files = request.files.getlist('resume-folder')
    if not resume_files:
        flash('No selected folder', 'error')
        return 'No selected folder'

    # Upload files to Azure Blob Storage
    blob_service_client = get_blob_service_client(AZURE_STORAGE_CONNECTION_STRING)
    upload_folder_to_blob(blob_service_client, AZURE_CONTAINER_NAME, resume_files)

    flash('Files Uploaded in Database', 'success')
    return redirect(url_for('form'))

@app.route('/submit', methods=['POST'])
def submit():
    skills = request.form.getlist('skills')  # This retrieves a list of checked skills
    additional_skills_input = request.form.get('additional_skills', '')
    additional_skills = [skill.strip() for skill in additional_skills_input.split(',') if skill.strip()]
    folder_selected = request.form.get('folder-select')
    # Combine checkbox skills and additional typed skills into one list
    skills = skills + additional_skills
    print("Received skills:", skills)  # This line prints the skills to the console
    folder_path = str(folder_selected)  
    csv_filename = 'resume_info.csv'
    csv_path = os.path.join('output', csv_filename)
    cities = set()
    with open('places.csv', 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            cities.add(row[0].lower())

    with open(csv_path, 'w', newline='') as csvfile:
        fieldnames = ['Name', 'Contact Number', 'Email', 'Skill', 'Location', 'Experience', 'Filename']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for filename, text in extract_text_from_blob_folder(blob_service_client, AZURE_CONTAINER_NAME, folder_path).items():
            if filename.endswith((".pdf", ".docx")):
                found_skills = search_skills_in_resume(text, skills)
                if found_skills:
                    name = extract_name(filename, text)
                    contact_number = extract_contact_number_from_resume(text)
                    email = extract_email_from_resume(text)
                    loc = get_location(text, cities)
                    experience = get_experience(filename)
                    writer.writerow({'Filename': filename, 'Name': name, 'Contact Number': contact_number, 'Email': email, 'Skill': ', '.join(found_skills), 'Location': loc, 'Experience': experience})
    flash('File Downloaded...', 'success')

    return send_from_directory(directory='output', path=csv_filename, as_attachment=True)  

def extract_text_from_pdf(blob_client):
    # Download the PDF blob content
    blob_content = blob_client.download_blob()
    stream = BytesIO()
    blob_content.readinto(stream)
    
    # Extract text from PDF using pdfplumber
    text = extract_text(stream)
    return text

def extract_text_from_blob_folder(blob_service_client, container_name, folder_name):
    blob_service_client = get_blob_service_client(AZURE_STORAGE_CONNECTION_STRING)
    container_client = blob_service_client.get_container_client(container_name)

    texts = {}  # Store text for each file
    for blob in container_client.list_blobs(name_starts_with=folder_name):
        # Extract text from each PDF blob in the folder
        blob_client = container_client.get_blob_client(blob)
        if blob.name.endswith('.pdf'):
            text = extract_text_from_pdf(blob_client)
            texts[blob.name] = text
        else:
            print(f"{blob.name} is not a PDF file. Skipping...")

    return texts


def extract_text_from_docx(docx_path):
 
    with open(docx_path, 'rb') as docx_file:
        result = mammoth.extract_raw_text(docx_file)
        text = result.value
    
    return text


def extract_contact_number_from_resume(text):
    pattern = r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
    match = re.search(pattern, text)
    if match:
        return match.group()
    return 'Not Found'

def extract_email_from_resume(text):
    pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    match = re.search(pattern, text)
    if match:
        return match.group()
    return 'Not Found'

def extract_name(filename, resume_text):
    if filename.lower().startswith("naukri_"):
        name_match = re.search(r"Naukri_([A-Za-z]+)", filename)
        name = name_match.group(1) if name_match else 'Unknown'
        return name.capitalize()
    
    else:
        nlp = spacy.load('en_core_web_sm')
        matcher = Matcher(nlp.vocab)
        patterns = [[{'POS': 'PROPN'}, {'POS': 'PROPN'}], [{'POS': 'PROPN'}, {'POS': 'PROPN'}, {'POS': 'PROPN'}], [{'POS': 'PROPN'}, {'POS': 'PROPN'}, {'POS': 'PROPN'}, {'POS': 'PROPN'}]]
        for pattern in patterns:
            matcher.add('NAME', patterns=[pattern])
        doc = nlp(resume_text)
        matches = matcher(doc)
        for match_id, start, end in matches:
            span = doc[start:end]
            return span.text
        return None
    
def get_location(text, city_set):
    text = re.sub(r'[^\w\s]', '', text.lower())
    text_words = text.split()
    for word in text_words:
        if word in city_set:
            return word
    return None
def get_experience(filename): #for naukri_ files
    experience_match = re.search(r"\[(\d+y_\d+m)\]", filename)
    experience = experience_match.group(1) if experience_match else 'Not Provided'
    return experience

def search_skills_in_resume(text, skills):
    found_skills = []
    for skill in skills:
        if skill.lower() in text.lower():
            found_skills.append(skill)
    return found_skills if found_skills else None

if __name__ == '__main__':
    app.run(debug=True)
