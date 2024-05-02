from flask import Flask, request, render_template, send_from_directory,flash,redirect,url_for
import os
import csv
import re
import mammoth #for docx files
from azure_upload import get_blob_service_client, upload_folder_to_blob #functions fetched from azure_upload.py
from pdfminer.high_level import extract_text #extracting text chunks from pdf files
import spacy  #for nlp (extracting names and skills)
from spacy.matcher import Matcher #comparing patterns found with grammatical context
app = Flask(__name__)

# Set the secret key
app.config['SECRET_KEY'] = 'rove2001'  # Replace 'your_secret_key_here' with your actual secret key

# Load SpaCy model globally to avoid reloading it on each request
nlp = spacy.load('en_core_web_sm')


AZURE_STORAGE_CONNECTION_STRING = 'AccountName=lzblobgenaipoc;AccountKey=Dr8dZzKKzLGAhGtexd2NkGl0YMJjl6T4uS6TP+xFWKeoH9IA73nXhmk28hUVrFRAwcRjZ2Gz0CV4+AStoIo6bg==;EndpointSuffix=core.windows.net;DefaultEndpointsProtocol=https;'
AZURE_CONTAINER_NAME = 'rohit'

@app.route('/')
def form():
    return render_template('form.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'resume-folder' not in request.files:
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

    # Combine checkbox skills and additional typed skills into one list
    skills = skills + additional_skills
    print("Received skills:", skills)  # This line prints the skills to the console
    folder_path = "cvs"  # Specify your folder path here
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

        for filename in os.listdir(folder_path):
            if filename.endswith((".pdf", ".docx")):  # Also check for .docx files
                resume_path = os.path.join(folder_path, filename)
                if filename.endswith(".pdf"):
                    text = extract_text_from_pdf(resume_path)
                elif filename.endswith(".docx"):
                    text = extract_text_from_docx(resume_path)

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

def extract_text_from_pdf(pdf_path):
    return extract_text(pdf_path)

def extract_text_from_docx(docx_path):
 
    with open(docx_path, 'rb') as docx_file:
        result = mammoth.extract_raw_text(docx_file)
        text = result.value
    
    return text

def extract_text_from_pdf(pdf_path):
    return extract_text(pdf_path)

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
def get_experience(filename):
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
