import pathlib
import secrets
from functools import wraps
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests
from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, session, Response, abort
from flask_wtf import FlaskForm
from flask_bootstrap import Bootstrap
from flask_wtf.file import FileAllowed
from werkzeug.security import generate_password_hash, check_password_hash
from wtforms import FileField, SubmitField, StringField, IntegerField, PasswordField, SelectField
from werkzeug.utils import secure_filename
import os
from wtforms.validators import InputRequired, DataRequired, NumberRange, EqualTo, Email, ValidationError
import os.path
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine, or_
import re
import csv
import io
from io import TextIOWrapper, StringIO
from flask_mail import Mail, Message
import requests
# import threading
# import boto3
# import argparse
# from rev_ai import apiclient
# import json
# from botocore.retries import bucket
# from google.cloud import speech_v1p1beta1 as speech
# from assemblyai import LanguageCode
# from rev_ai.apiclient import RevAiAPIClient
# import assemblyai as aai
# import time
# import whispers
# import gc
#trigger pipeline6

from flask_login import current_user
import pymysql

# from dotenv import load_dotenv
# load_dotenv()


# AssemblyAI API Key
# aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY")

app = Flask(__name__)
bootstrap = Bootstrap(app)

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json")

flow = Flow.from_client_secrets_file(
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email",
            "openid"],
    redirect_uri="http://127.0.0.1:5000/callback"
)
state = None

app.config['SECRET_KEY'] = ' '  #secret key
app.config['UPLOAD_FOLDER'] = 'static/files'

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql:// '  #db info
db = SQLAlchemy(app)
DB_URI = 'mysql+pymysql:// '  #db info
engine = create_engine(DB_URI)
Session = sessionmaker(bind=engine)

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

mail = Mail(app)

# # AWS
# transcribe_client = boto3.client('transcribe', aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
#                                  aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
#                                  region_name="ap-southeast-1")


# def start_transcription_job(audio_file_uri, job_name):
#     """Starts a new transcription job for the provided audio file."""
#     response = transcribe_client.start_transcription_job(
#         TranscriptionJobName=job_name,
#         Media={'MediaFileUri': audio_file_uri},
#         MediaFormat='mp3'  # Replace with your audio format (e.g., wav, flac)
#     )
#     return response['TranscriptionJob']['TranscriptionJobId']


# def get_transcription_job_status(job_name):
#     """Checks the status of a transcription job."""
#     response = transcribe_client.get_transcription_job(TranscriptionJobName='speech-to-text-1713762666')
#     return response['TranscriptionJob']['TranscriptionJobStatus']


# def get_transcription_result(job_name):
#     """Retrieves the transcript text once the job is complete."""
#     while True:
#         status = get_transcription_job_status(job_name)
#         if status == 'COMPLETED':
#             break
#         time.sleep(5)  # Adjust the delay between checks as needed
#     response = transcribe_client.get_transcription_job(TranscriptionJobName='speech-to-text-1713762666')
#     return response['TranscriptionJob']['Transcript']


class Movies(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    movie_name = db.Column(db.String(50), nullable=False)
    movie_file = db.Column(db.Text, nullable=False)
    created_for = db.Column(db.Text, nullable=False)
    transcripts = db.relationship('Transcripts', backref='movie', lazy=True)

    def __repr__(self):
        return '<MovieName %r>' % self.movie_name


class Transcripts(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'))  # Foreign Key
    start_time = db.Column(db.Float)
    end_time = db.Column(db.Float)
    speaker = db.Column(db.String(50))
    text = db.Column(db.Text)

    def __repr__(self):
        return f'<Transcript for Video ID: {self.movie_id}>'


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    profile_picture = db.Column(db.String(255))
    isAdmin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class MakeAdForm(FlaskForm):
    moviename = StringField('Movie Name', validators=[DataRequired()], render_kw={"placeholder": "Enter movie name"})
    file = FileField("File", validators=[InputRequired()])
    language = SelectField('Language', choices=[('en', 'English'), ('zh', 'Chinese')],
                           validators=[DataRequired()])
    speaker = IntegerField('Number of Speakers', validators=[DataRequired(), NumberRange(min=1, max=10)],
                           render_kw={"placeholder": "Enter number of speakers"})
    user = StringField('Created for ', validators=[DataRequired(), Email()],
                       render_kw={"placeholder": "Enter user's email"})
    submit = SubmitField('Transcribe')

    def validate_user(self, field):
        user_email = field.data
        user = User.query.filter_by(email=user_email).first()
        if user is None:
            raise ValidationError('The email entered does not exist in the database.')


class EditAdForm(FlaskForm):
    text = StringField('Transcript', validators=[DataRequired()])
    speakers = StringField('Speaker Name', validators=[DataRequired()])
    submit = SubmitField('Update')


class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])
    profile_picture = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')])
    submit = SubmitField('Register')

    def validate_password(self, password_field):
        password = password_field.data
        errors = []

        if len(password) < 8:
            errors.append('Password must be at least 8 characters long.')
        if not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter.')
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter.')
        if not re.search(r'\d', password):
            errors.append('Password must contain at least one digit.')
        if not re.search(r'[@$!%*?&]', password):
            errors.append('Password must contain at least one special character.')

        if errors:
            raise ValidationError(errors)

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already exists. Please choose a different one.')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


admin_routes = ['export_movie', 'deletead']


def create_tables():
    with app.app_context():
        db.create_all()
        print("Tables successfully created")


def generate_random_password(length=12):
    """Generates a random password of the specified length."""
    # Use secrets.token_urlsafe for cryptographically secure random strings
    password = secrets.token_urlsafe(length)
    return password


# Function to create initial admin user
def create_initial_admin_user(*args, **kwargs):
    admin_user = User.query.filter_by(email='admin@mail.com').first()
    if not admin_user:
        admin_user = User(username='Admin', email='admin@mail.com',
                          password_hash=generate_password_hash('Password123!'), isAdmin=True,
                          profile_picture='admin.png')
        db.session.add(admin_user)
        db.session.commit()


# Listen for table creation event
db.event.listen(db.metadata, 'after_create', create_initial_admin_user)


def combine_movie_transcript():
    # Write code to fetch movie and transcript details and combine them
    # For example:
    movies = Movies.query.all()
    combined_data = []
    for movie in movies:
        transcript_entries = Transcripts.query.filter_by(movie_id=movie.id).all()
        for entry in transcript_entries:
            combined_data.append({
                'Movie Name': movie.movie_name,
                'Start Time': entry.start_time,
                'End Time': entry.end_time,
                'Speaker': entry.speaker,
                'Text': entry.text
            })
    return combined_data


# 'Movie Id',
def generate_csv(data):
    output = io.StringIO()
    writer = csv.DictWriter(output,
                            fieldnames=['Movie Name', 'Movie File', 'Created For', 'Start Time', 'End Time', 'Speaker',
                                        'Text'])
    writer.writeheader()
    writer.writerows(data)
    return output.getvalue()


def decompile_csv(csv_file):
    # Decode the CSV file
    csv_file = TextIOWrapper(csv_file, encoding="utf-8-sig")

    # Read CSV data and store in the database
    reader = csv.DictReader(csv_file)
    for row in reader:
        # Extract data from each row and store in the database
        movie_name = row["Movie Name"]
        start_time = row["Start Time"]
        end_time = row["End Time"]
        speaker = row["Speaker"]
        text = row["Text"]

        # Example: Create entries in the database
        movie = Movies.query.filter_by(movie_name=movie_name).first()
        if movie:
            # Create transcript entry
            transcript_entry = Transcripts(start_time=start_time, end_time=end_time,
                                           speaker=speaker, text=text)
            db.session.add(transcript_entry)

    # Commit the changes to the database
    db.session.commit()


# fill in your mysql respective values

# app.config['MYSQL_HOST'] = 'mysql+pymysql://gabrqqq:mysqlmysql@gabrqqq.mysql.pythonanywhere-services.com/gabrqqq$fyp'
# app.config['MYSQL_PORT'] = 3306
# app.config['MYSQL_USER'] = 'gabrqqq'
# app.config['MYSQL_PASSWORD'] = "mysqlmysql"
# app.config['MYSQL_DB'] = "gabrqqq$fyp"
# mysql = MySQL(app)

@app.before_request
def before_request():
    if 'user_id' not in session and request.endpoint not in ['login', 'register', 'error404', 'google_login',
                                                             'callback']:
        # User is not logged in and trying to access a protected route,
        # redirect to login page
        return redirect(url_for('login'))


def check_admin(func):
    @wraps(func)
    def decorated_function(*args, **kwargs):
        # Check if the requested endpoint is in the list of admin routes
        if request.endpoint in admin_routes:
            # Check if the user is logged in and is an admin
            if 'user_id' not in session or not session.get('isAdmin', False):
                # Redirect to a different route or return an error response
                return redirect(url_for('playback'))  # Redirect to a route indicating unauthorized access
        return func(*args, **kwargs)

    return decorated_function


def check_logged_in():
    if 'user_id' in session:
        return redirect(url_for('index'))


@app.route("/", methods=['GET', 'POST'])
def index():
    return render_template('index.html')


@app.route("/Record", methods=['POST', 'GET'])
def Record():
    return render_template("record.html")


@app.route("/deletead/<int:movie_id>", methods=['GET', 'POST'])
@check_admin
def deletead(movie_id):
    movie_to_delete = Movies.query.get(movie_id)

    if request.method == "POST":
        if movie_to_delete:
            # Delete entries from the 'transcripts' table associated with the movie ID
            transcripts_to_delete = Transcripts.query.filter_by(movie_id=movie_id).all()
            for transcript in transcripts_to_delete:
                db.session.delete(transcript)

            # Delete the movie entry from the 'Movies' table
            db.session.delete(movie_to_delete)
            db.session.commit()
            print("Deleted")
            return redirect(url_for('playback'))
        else:
            print("Movie not found")


# # AssemblyAI
# @app.route("/makead", methods=['GET', 'POST'])
# def makead():
#     form = MakeAdForm()
#     if form.validate_on_submit():
#         moviename = form.moviename.data
#         file = form.file.data
#         createdfor = form.user.data
#         # Save the file to your desired location
#         file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
#         file.save(file_path)
#         print("File has been uploaded")
#
#         # Retrieve other form data
#         speakers = form.speaker.data
#         filename = file.filename
#         langcode = LanguageCode(form.language.data)
#
#         config = aai.TranscriptionConfig(
#             speaker_labels=True,
#             speakers_expected=speakers,
#             language_code=langcode
#         )
#
#         # Transcribe the audio from the video file
#         transcript = aai.Transcriber().transcribe(file_path, config)
#
#         # # Open the file for writing the transcription
#         # with open("transcription.txt", 'w') as f:
#         #     for utterance in transcript.utterances:
#         #         start_time = utterance.start / 1000
#         #         end_time = utterance.end / 1000
#         #         text = utterance.text
#         #
#         #         # Write the text only at its start time
#         #         f.write(f"[{start_time} - {end_time}] Speaker {utterance.speaker}: {text}\n")
#         #
#         # # Read the transcription data from the file
#         # with open('transcription.txt', 'r') as f:
#         #     data = f.read()
#
#         try:
#             # Create a new movie instance
#             movie = Movies(movie_name=moviename, movie_file=filename, created_for=createdfor
#                            )
#             db.session.add(movie)
#             db.session.commit()
#
#             # Create transcript entries for the movie
#             for utterance in transcript.utterances:
#                 start_time = utterance.start / 1000
#                 end_time = utterance.end / 1000
#                 text = utterance.text
#
#                 # Create transcript entry
#                 transcript_entry = Transcripts(movie_id=movie.id, start_time=start_time,
#                                                end_time=end_time, speaker=utterance.speaker, text=text)
#                 db.session.add(transcript_entry)
#
#             # Commit transcript entries
#             db.session.commit()
#             print("Data inserted successfully")
#         except Exception as e:
#             print(f"Error inserting data into the database: {str(e)}")
#
#         return redirect(url_for('playback'))
#     else:
#         print("Form validation failed")
#         return render_template('makead.html', form=form)


GLADIA_API_KEY = os.getenv("GLADIA_API_KEY")
GLADIA_API_URL = 'https://api.gladia.io/v2/transcription'

def audio_transcription(filepath: str, speakers,langcode):
            # Define API key as a header
            headers = {'x-gladia-key': f'{os.getenv("GLADIA_API_KEY")}'}

            filename, file_ext = os.path.splitext(filepath)
            # Prepare data for API request
            with open(filepath, 'rb') as audio:
                files = {
                    'audio': (filename, audio, f'audio/{file_ext[1:]}'),  # Specify audio file type
                    'toggle_diarization': True,  # Toggle diarization option
                    'diarization_min_speakers': (None, speakers),  # Set the maximum number of speakers for diarization
                    'output_format': (None, 'txt'),  # Specify output format as text
                    'toggle_noise_reduction': True,
                    'language': langcode
                }

                print('Sending request to Gladia API')

                # Make a POST request to Gladia API
                response = requests.post('https://api.gladia.io/audio/text/audio-transcription/', headers=headers, files=files)

                if response.status_code == 200:
                    # If the request is successful, parse the JSON response
                    response = response.json()

                    # Extract the transcription from the response
                    prediction = response['prediction']

                    # Write the transcription to a text file
                    with open('transcription.txt', 'w', encoding='utf-8') as f:
                        f.write(prediction)

                    return response

                else:
                    # If the request fails, print an error message and return the JSON response
                    print('Request failed')
                    return response.json()


# Gladia STT
@app.route("/makead", methods=['GET', 'POST'])
def makead():
    form = MakeAdForm()
    if form.validate_on_submit():
        moviename = form.moviename.data
        file = form.file.data
        createdfor = form.user.data
        speakers = form.speaker.data
        filename = file.filename
        langcode = form.language.data

        # Save the uploaded file securely
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
        file.save(file_path)

        response = audio_transcription(file_path, speakers, langcode)

        # Create a new movie instance
        movie = Movies(movie_name=moviename, movie_file=filename, created_for=createdfor
                       )
        db.session.add(movie)
        db.session.commit()

        transcription_data = response['prediction_raw']['transcription']
        combined_text = ''
        start_time = None
        end_time = None
        speaker = None
        max_gap_seconds = 2
        # Create transcript entries for the movie
        for utterance in transcription_data:
            current_speaker = utterance['speaker']
            current_text = utterance['transcription']
            current_start_time = utterance['time_begin']
            current_end_time = utterance['time_end']

            # If there's no ongoing combination or if the speaker changes, add the ongoing combination as a separate entry
            if combined_text == '' or current_speaker != speaker or current_start_time - end_time > max_gap_seconds:
                # If there's an ongoing combination, add it as a separate entry
                if combined_text != '':
                    # Create transcript entry for the ongoing combination
                    transcript_entry = Transcripts(movie_id=movie.id, start_time=start_time,
                                                   end_time=end_time, speaker=speaker, text=combined_text)
                    db.session.add(transcript_entry)

                # Start a new combination with the current utterance
                combined_text = current_text
                start_time = current_start_time
                speaker = current_speaker
                end_time = current_end_time

            else:
                # Combine the text of the ongoing combination and the current utterance
                combined_text += " " + current_text
                end_time = current_end_time

        # Add the last combination as a separate entry if any
        if combined_text != '':
            transcript_entry = Transcripts(movie_id=movie.id, start_time=start_time,
                                           end_time=end_time, speaker=speaker, text=combined_text)
            db.session.add(transcript_entry)


        # Commit transcript entries
        db.session.commit()
        print("Data inserted successfully")

        return redirect(url_for('playback'))


    # Indentation fixed here:
    else:
        return render_template('makead.html', form=form)



# # Google STT
#
# # Function to transcribe audio file using Google Speech-to-Text
# def transcribe_audio(file_path, speakers, langcode):
#     client = speech.SpeechClient()
#
#     with io.open(file_path, "rb") as audio_file:
#         content = audio_file.read()
#
#     # Check file extension (optional)
#     if file_path.endswith(".mp3"):
#         config = {
#             "encoding": speech.RecognitionConfig.AudioEncoding.MP3,
#             "sample_rate_hertz": 8000,
#             "language_code": langcode,
#             "enable_speaker_diarization": True,
#             "diarization_speaker_count": speakers
#         }
#     else:
#         # Use default encoding (e.g., LINEAR16) for non-MP3 files
#         config = {
#             "encoding": speech.RecognitionConfig.AudioEncoding.LINEAR16,
#             "sample_rate_hertz": 8000,
#             "language_code": langcode,
#             "enable_speaker_diarization": True,
#             "diarization_speaker_count": speakers
#         }
#
#     audio = {"content": content}
#
#     operation = client.long_running_recognize(request={"config": config, "audio": audio})
#
#     print("Waiting for operation to complete...")
#     response = operation.result(timeout=90)
#
#     transcripts = []
#
#     for result in response.results:
#             # for word in result.alternatives[0].words:
#         #
#         #     transcript = word.word
#         #     speaker_tag = word.speaker_tag
#         #
#         #     transcripts.append((transcript,  speaker_tag))
#         transcripts.append(result.alternatives[0].transcript)
#
#     print(transcripts)
#     return transcripts
#
#
#
# @app.route("/makead", methods=['GET', 'POST'])
# def makead():
#     form = MakeAdForm()
#     if form.validate_on_submit():
#         moviename = form.moviename.data
#         file = form.file.data
#         createdfor = form.user.data
#         # Save the file to your desired location
#         file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
#         file.save(file_path)
#         print("File has been uploaded")
#
#         # Retrieve other form data
#         speakers = form.speaker.data
#         langcode = form.language.data
#
#         # Transcribe the audio from the video file using Google Speech-to-Text
#         transcripts = transcribe_audio(file_path, speakers, langcode)
#
#         try:
#             # Create a new movie instance
#             movie = Movies(movie_name=moviename, movie_file=file.filename, created_for=createdfor)
#             db.session.add(movie)
#             db.session.commit()
#
#             # Create transcript entries for the movie
#             for transcript, speaker_tag in transcripts:
#                 transcript_entry = Transcripts(movie_id=movie.id, text=transcript, speaker=speaker_tag)
#                 db.session.add(transcript_entry)
#
#             # Commit transcript entries
#             db.session.commit()
#             print("Data inserted successfully")
#         except Exception as e:
#             print(f"Error inserting data into the database: {str(e)}")
#
#         return redirect(url_for('playback'))
#     else:
#         print("Form validation failed")
#         return render_template('makead.html', form=form)
#
#
# def handle_transcript_response(response_data):
#     transcript_data = response_data['TranscriptionJob']['Transcript']
#     transcript_uri = transcript_data['TranscriptFileUri']
#
#     # Download the transcript JSON
#     try:
#         response = requests.get(transcript_uri)
#         response.raise_for_status()  # Raise an exception for non-2xx status codes
#     except requests.exceptions.RequestException as e:
#         print(f"Error downloading transcript: {e}")
#         return
#
#     # Parse the downloaded JSON
#     try:
#         transcript_data = response.json()
#     except json.JSONDecodeError as e:
#         print(f"Error parsing transcript JSON: {e}")
#         return
#
#     # Extract content, start time, and end time for each item in 'items'
#     items = transcript_data.get('results', {}).get('items', [])  # Use .get() for safer access
#     if items:
#         for item in items:
#             content = item.get('alternatives', [{}])[0].get('content', '')  # Extract content
#             start_time = item.get('start_time', '')  # Extract start time
#             end_time = item.get('end_time', '')  # Extract end time
#             print(f"Content: {content}, Start Time: {start_time}, End Time: {end_time}")
#     else:
#         print("No items found in transcript")


# # AWS
# @app.route("/makead", methods=['GET', 'POST'])
# def makead():
#     form = MakeAdForm()
#     if form.validate_on_submit():
#         moviename = form.moviename.data
#         file = form.file.data
#         createdfor = form.user.data
#
#         # Save the file to your desired location
#         file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
#         try:
#             file.save(file_path)
#             print("File has been uploaded")
#         except Exception as e:
#             print(f"Error saving uploaded file: {str(e)}")
#             # Consider returning an error message to the user here
#
#         # Retrieve other form data (assuming validation happens within the form itself)
#         speakers = form.speaker.data
#         filename = file.filename
#         langcode = form.language.data
#
#         # Transcribe the audio from the video file
#         s3_client = boto3.client('s3')
#         s3_bucket_name = " "  # Replace with your bucket name
#         s3_resource = boto3.resource(
#             's3',
#             aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
#             aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
#         )
#
#         bucket = s3_resource.Bucket(' ') #your bucket name
#         # Assuming 'file' is the form field containing the uploaded video
#         video_file = form.file.data
#         video_filename = str(secure_filename(video_file.filename))  # Maintain filename security
#         print(video_filename)
#         audio_file_uri = f"s3://{s3_bucket_name}/{video_filename}"
#
#         # Upload the video to S3
#         # s3_client.upload_file(video_file, s3_bucket_name, video_filename, ExtraArgs={'ContentType': video_file.content_type})
#         # bucket.Object(file.filename).put(Body=file.read())
#         file.seek(0)
#         bucket.upload_fileobj(file, Key=video_filename)
#         print(f"Video uploaded to S3: {video_filename}")
#
#         # Generate a unique job name
#         job_name = f"speech-to-text-{int(time.time())}"
#
#         # Start the transcription job
#         job_id = transcribe_client.start_transcription_job(Media={"MediaFileUri": audio_file_uri},
#                                                         LanguageCode=langcode,
#                                                         TranscriptionJobName=job_name,
#                                                         Settings={'ShowSpeakerLabels': True, 'MaxSpeakerLabels': speakers})
#
#         # Wait for the job to complete
#         time.sleep(30)
#         status = get_transcription_job_status(job_name)
#         print(status)
#         while status not in ['COMPLETED', 'FAILED']:
#             time.sleep(10)  # Adjust wait time as needed
#             status = get_transcription_job_status(job_name)
#             print(status)
#
#         # Get the transcript text
#         if status == 'COMPLETED':
#             # Download and parse transcript (using handle_transcript_response)
#             transcript_response = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
#             transcript_data = handle_transcript_response(transcript_response)
#
#             if transcript_data:  # Check if transcript data was extracted successfully
#                 try:
#                     # Create a new movie instance
#                     movie = Movies(movie_name=moviename, movie_file=filename, created_for=createdfor)
#                     db.session.add(movie)
#                     db.session.commit()
#
#                     # Create transcript entries for the movie (assuming transcript_data is a list of utterances)
#                     for item in transcript_data:
#                         start_time = item.get('start') / 1000  # Assuming start in milliseconds
#                         end_time = item.get('end') / 1000  # Assuming end in milliseconds
#                         speaker = item.get('speaker')
#                         text = item.get('text')
#
#                         # Create transcript entry
#                         transcript_entry = Transcripts(movie_id=movie.id, start_time=start_time,
#                                                        end_time=end_time, speaker=speaker, text=text)
#                         db.session.add(transcript_entry)
#
#                     # Commit transcript entries in a single commit after processing all utterances
#                     db.session.commit()
#                     print("Data inserted successfully")
#                 except Exception as e:
#                     print(f"Error inserting data into the database: {str(e)}")
#                     # Consider rolling back the movie creation if transcript saving fails (optional)
#                     # db.session.rollback()
#
#             else:  # Handle case where transcript data couldn't be extracted
#                 print("Error: Unable to extract transcript data")
#
#         return redirect(url_for('playback'))
#
#     else:
#         print("Form validation failed")
#         return render_template('makead.html', form=form)


# #WhisperX (deprecated)
# @app.route("/makead", methods=['GET', 'POST'])
# def makead():
#     form = MakeAdForm()
#     if form.validate_on_submit():
#         moviename = form.moviename.data
#         file = form.file.data
#         createdfor = form.user.data
#         # Save the file to your desired location
#         file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
#         file.save(file_path)
#         print("File has been uploaded")
#
#         # Retrieve other form data
#         speakers = form.speaker.data
#         filename = file.filename
#         langcode = LanguageCode(form.language.data)
#
#         device = "cuda"
#         audio_file = filename
#         batch_size = 16 # reduce if low on GPU mem
#         compute_type = "float16" # change to "int8" if low on GPU mem (may reduce accuracy)
#
#         # 1. Transcribe with original whisper (batched)
#         print("loading model")
#         model = whisperx.load_model("large-v2", device, compute_type=compute_type)
#         print("loading audio")
#         audio = whisperx.load_audio(audio_file)
#         print("transcribing audio")
#         result = model.transcribe(audio, batch_size=batch_size)
#
#         print(result["segments"]) # before alignment
#
#         # 2. Align whisper output
#         model_a, metadata = whisperx.load_align_model(language_code=result["language"], device=device)
#         result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
#
#         print(result["segments"]) # after alignment
#
#         # 3. Assign speaker labels
#         diarize_model = whisperx.DiarizationPipeline(use_auth_token=os.getenv("HF_ACCESS_TOKEN"), device=device)
#
#         # add min/max number of speakers if known
#         diarize_segments = diarize_model(audio, min_speakers=1, max_speakers=speakers)
#
#
#         result = whisperx.assign_word_speakers(diarize_segments, result)
#         print(diarize_segments)
#         print(result["segments"]) # segments are now assigned speaker IDs
#
#         try:
#             # Create a new movie instance
#             movie = Movies(movie_name=moviename, movie_file=filename, created_for=createdfor
#                            )
#             db.session.add(movie)
#             db.session.commit()
#
#             # Create transcript entries for the movie
#             for utterance in result.utterances:
#                 start_time = utterance.start / 1000
#                 end_time = utterance.end / 1000
#                 text = utterance.text
#
#                 # Create transcript entry
#                 transcript_entry = Transcripts(movie_id=movie.id, start_time=start_time,
#                                                end_time=end_time, speaker=utterance.speaker, text=text)
#                 db.session.add(transcript_entry)
#
#             # Commit transcript entries
#             db.session.commit()
#             print("Data inserted successfully")
#         except Exception as e:
#             print(f"Error inserting data into the database: {str(e)}")
#
#         return redirect(url_for('playback'))
#     else:
#         print("Form validation failed")
#         return render_template('makead.html', form=form)

# #RevAi
# @app.route("/makead", methods=['GET', 'POST'])
# def makead():
#     form = MakeAdForm()
#     if form.validate_on_submit():
#         moviename = form.moviename.data
#         file = form.file.data
#         createdfor = form.user.data
#         speakers = form.speaker.data
#         filename = file.filename
#         langcode = form.language.data
#
#         # Save the uploaded file securely (replace with error handling)
#         file_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
#         file.save(file_path)
#
#         # Rev.ai access token from environment variable
#         token = os.getenv("REV_ACCESS_TOKEN")
#
#         # Use Rev.ai for speech-to-text
#         client = RevAiAPIClient(token)  # Assuming RevAiAPIClient is imported
#         job = client.submit_job_local_file(file_path)
#
#         # Function to check job status (improvement)
#         def check_job_status(job_id, client):
#             while True:
#                 job_details = client.get_job_details(job_id)
#                 if job_details.status == 'transcribed':
#                     print("Job completed!")
#                     return job_details
#                 else:
#                     print(f"Job status: {job_details.status}. Waiting...")
#                     time.sleep(5)  # Wait 5 seconds before next check
#
#         # Wait for completion and get details (improvement)
#         completed_job = check_job_status(job.id, client)
#
#         # Retrieve transcript text
#         transcript_data = client.get_transcript_json(job.id)
#         # print(transcript_data)
#
#         # Extract utterances
#         utterances = []
#         for monologue in transcript_data['monologues']:
#             speaker = monologue.get('speaker')  # Assuming speaker information might not be available
#             for element in monologue['elements']:
#                 if element['type'] == 'text':
#                     transcription = element['value']
#                     time_begin = element['ts']
#                     time_end = element['end_ts']
#
#                     utterances.append({
#                         'speaker': speaker,  # Use the speaker ID for the entire monologue
#                         'transcription': transcription,
#                         'time_begin': time_begin,
#                         'time_end': time_end,
#                     })
#
#         # Create a new movie instance
#         movie = Movies(movie_name=moviename, movie_file=filename, created_for=createdfor)
#         db.session.add(movie)
#         db.session.commit()
#
#         combined_text = ''
#         start_time = None
#         end_time = None
#         speaker = None
#         max_gap_seconds = 2
#
#         # Create transcript entries with merged text for utterances within a time gap
#         for utterance in utterances:
#             current_speaker = utterance['speaker']
#             current_text = utterance['transcription']
#
#             # Check if information for time_begin and time_end is available from Rev.ai (replace logic if it is)
#             if utterance.get('time_begin') is not None and utterance.get('time_end') is not None:
#                 current_start_time = utterance['time_begin']
#                 current_end_time = utterance['time_end']
#             else:
#                 # Use a placeholder value if timestamps are not provided
#                 current_start_time = 0  # Replace with appropriate placeholder
#                 current_end_time = 0  # Replace with appropriate placeholder
#
#             # Combine utterances with a small time gap
#             if combined_text == '' or current_speaker != speaker or current_start_time - end_time > max_gap_seconds:
#                 if combined_text != '':
#                     # Create transcript entry for the ongoing combination
#                     transcript_entry = Transcripts(movie_id=movie.id, start_time=start_time,
#                                                    end_time=end_time, speaker=speaker, text=combined_text)
#                     db.session.add(transcript_entry)
#
#                 combined_text = current_text
#                 start_time = current_start_time
#                 speaker = current_speaker
#                 end_time = current_end_time
#
#             else:
#                 combined_text += " " + current_text
#                 end_time = current_end_time
#
#         # Add the last combination as a separate entry if any
#         if combined_text != '':
#             transcript_entry = Transcripts(movie_id=movie.id, start_time=start_time,
#                                            end_time=end_time, speaker=speaker, text=combined_text)
#             db.session.add(transcript_entry)
#
#         # Commit transcript entries
#         db.session.commit()
#
#         print("Data inserted successfully")
#
#         return redirect(url_for('playback'))
#
#
#     # Indentation fixed here:
#     else:
#         print("Form validation failed")
#         return render_template('makead.html', form=form)

@app.route("/Playback", methods=['GET', 'POST'])
def playback():
    # Check if user is logged in
    if 'user_id' in session:
        user_id = session['user_id']
        user = User.query.get(user_id)
        if user:
            is_admin = user.isAdmin
            user_email = user.email

            # Filter movies based on user's permissions
            if is_admin:
                query = Movies.query.all()  # Admin can view all movies
            else:
                query = Movies.query.filter(or_(Movies.created_for == user_email)).all()
    else:
        # Redirect user to login if not logged in
        return redirect(url_for('login'))

    return render_template('playback.html', query=query)


@app.route("/view/<int:movie_id>", methods=['GET', 'POST'])
def view(movie_id):
    # Query the database to retrieve the movie by ID
    movie = Movies.query.get(movie_id)

    if movie:
        transcripts = Transcripts.query.filter_by(movie_id=movie_id).all()
        transcript_data = [{
            'id': trans.id,
            'start_time': trans.start_time,
            'end_time': trans.end_time,
            'speaker': trans.speaker,
            'text': trans.text
        } for trans in transcripts]

        created_for = movie.created_for
        name = movie.movie_name
        file = movie.movie_file

        return render_template('view.html', name=name, file=file, created_for=created_for, trans=transcript_data)
    else:
        return "Movie not found"


@app.route('/editad/<int:movie_id>', methods=['GET', 'POST'])
def editad(movie_id):
    form = EditAdForm()  # Create an instance of the form

    if request.method == 'POST':
        speaker = request.form['speaker']
        new_name = request.form['new_name']

        # Update the speaker name in all transcripts for the selected movie
        transcripts = Transcripts.query.filter_by(movie_id=movie_id, speaker=speaker).all()
        for transcript in transcripts:
            transcript.speaker = new_name

        # Commit the changes to the database
        db.session.commit()

        # Redirect to a relevant page
        return redirect(url_for('editad', movie_id=movie_id))

    # Fetch all unique speaker names for the selected movie
    unique_speakers = set(Transcripts.query.filter_by(movie_id=movie_id).with_entities(Transcripts.speaker).distinct())

    # Extract the speaker names from the tuples and convert them into a list
    speakers = [speaker[0] for speaker in unique_speakers]

    return render_template('editad.html', form=form, speakers=speakers)


@app.route("/save_transcripts", methods=['POST'])
def save_transcripts():
    if request.method == 'POST':
        edited_transcripts = request.json['edited_transcripts']
        try:
            for edited_transcript in edited_transcripts:
                transcript_id = edited_transcript['id']
                new_speaker = edited_transcript['speaker']  # Update the speaker name
                new_text = edited_transcript['text']
                print(transcript_id, new_speaker, new_text)
                transcript = Transcripts.query.get(transcript_id)
                if transcript:
                    transcript.speaker = new_speaker  # Update the speaker name in the transcript object
                    transcript.text = new_text
                    db.session.commit()
            return jsonify({'success': True, 'message': 'Transcripts saved successfully'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})


UPLOAD_FOLDER = 'static/files/Images'


@app.route('/register', methods=['GET', 'POST'])
def register():
    if check_logged_in():  # Check if the user is already logged in
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        email = form.email.data
        username = form.username.data
        password = form.password.data
        confirm_password = form.confirm_password.data
        profile_picture = request.files['profile_picture'] if 'profile_picture' in request.files else None
        file = form.profile_picture.data

        # Check if a file was provided
        if file:
            filename = secure_filename(file.filename)
            file.save(os.path.join(UPLOAD_FOLDER, filename))
            profile_picture_filename = filename  # Save the filename to use in the user object
        else:
            profile_picture_filename = 'usericon.png'  # Use default profile picture

        new_user = User(email=email, username=username, profile_picture=profile_picture_filename)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful. You can now log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)


@app.route("/export_movie/<int:movie_id>")
@check_admin
def export_movie(movie_id):
    # Fetch the selected movie from the database
    movie = Movies.query.get(movie_id)
    if not movie:
        # flash("Selected movie not found", "error")
        return redirect(url_for("playback"))

    # Fetch transcript entries for the selected movie
    transcript_entries = Transcripts.query.filter_by(movie_id=movie.id).all()

    # Combine movie and transcript details
    combined_data = []
    for entry in transcript_entries:
        combined_data.append({
            'Movie Name': movie.movie_name,
            'Movie File': movie.movie_file,
            'Created For': movie.created_for,
            'Start Time': entry.start_time,
            'End Time': entry.end_time,
            'Speaker': entry.speaker,
            'Text': entry.text
        })

    # Generate CSV file
    output = generate_csv(combined_data)

    # Set dynamic file name based on the movie name
    file_name = f"{movie.movie_name}_transcript.csv"

    # Create a Flask-Mail message
    msg = Message(subject=f"Transcript for {movie.movie_name}",
                  sender="gabrielquek500@gmail.com",
                  recipients=[movie.created_for])  # Send to the recipient specified in movie.created_for
    msg.body = f"Transcript file for {movie.movie_name} is attached."

    # Attach the CSV file to the email message
    msg.attach(filename=file_name, content_type="text/csv", data=output)

    # Send the email
    mail.send(msg)

    # flash("Exported movie sent to recipient", "success")
    return redirect(url_for("playback"))


@app.route("/decompile_movies", methods=["POST"])
def decompile_movies():
    # Check if a CSV file was provided in the request
    if "file" not in request.files:
        # flash("No file part", "import_error")
        return redirect(request.url)

    file = request.files["file"]

    # Check if the file is empty
    if file.filename == "":
        # flash("No selected file", "import_error")
        return redirect(request.url)

    try:
        # Read CSV data
        file_text = file.stream.read().decode("utf-8-sig")
        reader = csv.DictReader(StringIO(file_text))

        # Iterate over each row in the CSV
        for row in reader:
            # Extract data from each row
            movie_name = row["Movie Name"]
            movie_file = row["Movie File"]
            created_for = row["Created For"]
            start_time = row["Start Time"]
            end_time = row["End Time"]
            speaker = row["Speaker"]
            text = row["Text"]

            # Fetch the movie from the database or create a new one if it doesn't exist
            movie = Movies.query.filter_by(movie_name=movie_name).first()
            if not movie:
                movie = Movies(movie_name=movie_name, movie_file=movie_file, created_for=created_for)
                db.session.add(movie)
                db.session.commit()  # Commit the movie to the database to obtain its id

            # Now the movie has an id, so you can safely create the transcript entry
            transcript = Transcripts(movie_id=movie.id, start_time=start_time, end_time=end_time,
                                     speaker=speaker, text=text)

            # Add the transcript entry to the session
            db.session.add(transcript)

        # Commit the changes to the database after all transcript entries have been added
        db.session.commit()

        # flash("Import successful", "success")
        return redirect(url_for("playback"))

    except Exception as e:
        # flash(f"Error importing data: {e}", "error")
        return redirect(request.url)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if check_logged_in():  # Check if the user is already logged in
        return redirect(url_for('index'))

    form = LoginForm()

    if form.validate_on_submit():
        # Check if the credentials are valid
        email = form.email.data
        password = form.password.data
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            session['user_id'] = user.id
            session['profile_picture'] = user.profile_picture
            session['email'] = user.email
            session['isAdmin'] = user.isAdmin  # Assuming isAdmin is a boolean attribute of the User model
            # Redirect to the appropriate page after successful login
            return redirect(url_for('index'))
        else:
            # Invalid credentials, show errors on the form
            form.email.errors.append('Invalid email or password.')
            form.password.errors.append('Invalid email or password.')

    # Get Google login URL
    google_login_url = url_for('google_login', _external=True)

    return render_template('login.html', form=form, google_login_url=google_login_url)


# Google login route
@app.route('/google-login')
def google_login():
    authorization_url, state = flow.authorization_url()
    session["state"] = state
    return redirect(authorization_url)


@app.route("/callback")
def callback():
    # Check session state to prevent CSRF attacks
    if "state" not in session or session["state"] != request.args.get("state"):
        abort(403)

    try:
        flow.fetch_token(authorization_response=request.url)

        # Verify the token and retrieve user information
        credentials = flow.credentials
        request_session = requests.session()
        cached_session = cachecontrol.CacheControl(request_session)
        token_request = google.auth.transport.requests.Request(session=cached_session)
        id_info = id_token.verify_oauth2_token(
            id_token=credentials._id_token,
            request=token_request,
            audience=GOOGLE_CLIENT_ID
        )
        # print(id_info)
        if id_info is None:
            # Token verification failed, handle accordingly
            print("Error: Token verification failed")
            abort(500)

        useremail = id_info.get('email')
        session["google_id"] = id_info.get("sub")
        session["name"] = id_info.get("name")

        # Check if the user exists in the database
        existing_user = User.query.filter_by(email=useremail).first()

        if existing_user:
            # User exists, log them in
            session['user_id'] = existing_user.id
            session['email'] = existing_user.email
            session['profile_picture'] = id_info.get('picture')
            session['isAdmin'] = existing_user.isAdmin
        else:
            # New user, register them
            new_user = User(
                email=id_info.get('email'),
                username=id_info.get('name')[:20],  # Truncate username to 20 characters (optional)
                profile_picture=id_info.get('picture'),
                isAdmin=False,
                # Generate a random password and hash it using Werkzeug security
                password_hash=generate_password_hash(generate_random_password())
            )
            db.session.add(new_user)
            db.session.commit()

            # Log the new user in
            session['user_id'] = new_user.id
            session['email'] = new_user.email
            session['profile_picture'] = new_user.profile_picture
            session['isAdmin'] = new_user.isAdmin

        return redirect(url_for('index'))

    except Exception as e:
        # Handle errors (e.g., invalid token)
        print("Error:", e)
        abort(500)


@app.route('/logout')
def logout():
    session.pop('user_id', None)  # Remove user ID from the session
    return redirect(url_for('login'))  # Redirect to login page after logout


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error404.html'), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return render_template('error405.html'), 405


@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error500.html'), 500


if __name__ == "__main__":
    create_tables()
    app.run(debug=True)
