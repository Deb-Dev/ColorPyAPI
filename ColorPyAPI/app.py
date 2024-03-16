from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from decompose.decomposer import decompose
from PIL import Image
from decompose.utils import images_to_ORA
import zipfile
import os
import time
import boto3
from botocore.exceptions import NoCredentialsError

# Setup AWS S3 client
s3_client = boto3.client(
    's3',
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)


app = Flask(__name__)

if __name__ == "__main__":
    app.run()

@app.route('/')
def hello_world():
    return jsonify(message="Hello, World!")

@app.route('/upload_and_decompose', methods=['POST'])
def upload_and_decompose():
    # 1. Receive a file from the client
    file = request.files['file']

    # 2. Validate the file (this is a very basic validation)
    if file and allowed_file(file.filename):
        # 3. Decompose the file (this is a placeholder - replace with your own logic)
        results = decompose_file(file)

        # 4. Return a response to the client
        return jsonify(results), 200
    else:
        return jsonify({'error': 'Invalid file'}), 400
    
def decompose_file(file):
    filename = secure_filename(file.filename)
    file.save(filename)

    img = Image.open(filename)
    layers = decompose(img)
    images_to_ORA(layers).save("img.ora")

    extract_png_from_ora('img.ora', 'output_folder_path')

    # Zip the extracted files
    zipf = zipfile.ZipFile('ExtractedFiles.zip', 'w', zipfile.ZIP_DEFLATED)
    zipdir('output_folder_path', zipf)
    zipf.close()

    # Upload the zip file to S3
    upload_to_aws('ExtractedFiles.zip', 'image-extracted-deb', 'ExtractedFiles.zip')

    # Generate the S3 URL for the uploaded file
    s3_url = generate_s3_url('image-extracted-deb', 'ExtractedFiles.zip')

    return {'status': 'success', 's3_url': s3_url}

def upload_to_aws(local_file, bucket, s3_file):
    try:
        s3_client.upload_file(local_file, bucket, s3_file)
        print("Upload Successful")
        return True
    except FileNotFoundError:
        print("The file was not found")
        return False
    except NoCredentialsError:
        print("Credentials not available")
        return False

def generate_s3_url(bucket, s3_file):
    s3_url = f"https://{bucket}.s3.amazonaws.com/{s3_file}"
    return s3_url


def extract_png_from_ora(ora_file_path, extract_to_folder):
    if not os.path.exists(extract_to_folder):
        os.makedirs(extract_to_folder)
    
    with zipfile.ZipFile(ora_file_path, 'r') as zip_ref:
        png_files = [f for f in zip_ref.namelist() if f.lower().endswith('.png')]
        
        for png_file in png_files:
            zip_ref.extract(png_file, extract_to_folder)

def zipdir(path, ziph):
    # ziph is zipfile handle
    for root, dirs, files in os.walk(path):
        for file in files:
            ziph.write(os.path.join(root, file), 
                       os.path.relpath(os.path.join(root, file), 
                                       os.path.join(path, '..')))

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS