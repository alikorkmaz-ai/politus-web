from flask import Flask, render_template, request, jsonify, send_from_directory, render_template_string
from pymongo import MongoClient
import os
import openai
from dotenv import load_dotenv
from rag.vectorstore import load_vectorstore  # RAG vektör veritabanı
from rag.query import answer_query  # RAG sorgu işleyicisi
from langchain_huggingface import HuggingFaceEmbeddings
from bson.objectid import ObjectId  # MongoDB'deki ObjectId'yi string'e çevirmek için

load_dotenv()

# Environment değişkenlerini al
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# MongoDB Bağlantısı
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

app = Flask(__name__)

# FAISS Veritabanını Yükle (RAG İçin)
retriever = load_vectorstore()
# Initialize embedding model
embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

# PDF Dosyaları İçin
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Liste içeren alanlar (MongoDB'de array olarak saklanan alanlar)
list_fields = [
    "gender", "occupation", "content_purpose", "age_group_about",
    "gender_about", "sexual_orientation_about", "ethnicity_about",
    "education_level_about", "disability_status_about", "disability_type_about",
    "migration_status_about", "marital_status_about", "urban_rural_about",
    "medical_condition_about", "religion_about", "political_view_about", "content_location"
]


@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/chatbot')
def chatbot():
    """Chatbot arayüzü için HTML sayfasını yükler"""
    return render_template('chatbot.html')


@app.route("/correction")
def text_moderation():
    return render_template("correction.html")

@app.route('/query', methods=['POST'])
def query_endpoint():
    """Kullanıcının sorduğu soruları RAG sistemine iletir ve yanıt döndürür."""
    data = request.get_json()
    query = data.get("query", "").strip()

    if not query:
        return jsonify({"error": "Sorgu boş olamaz"}), 400

    answer = answer_query(query, retriever, embedding_model)

    # ✅ Debugging: Print response before returning
    print("\n=== 🔍 [DEBUG] Final Response to Frontend ===")
    print(answer)
    print("=============================================\n")

    return jsonify({"query": query, "answer": answer})  # ✅ Ensure JSON response


@app.route('/filter', methods=['POST'])
def filter_data():
    filters = request.json.get('filters', {})
    query = {}

    print("### BACKEND'E GELEN FİLTRELER ###", filters)  # **Debugging için**

    for key, value in filters.items():
        if value and value != 'all':
            corrected_key = key.replace('-', '_')

            # **Hatalı publication_start_year ve publication_end_year sorgularını kaldırıyoruz**
            if corrected_key in ["publication_start_year", "publication_end_year"]:
                continue  # Bu alanlar kullanılmamalı

            # **Eğer yıl filtresi ise doğru ekle**
            if corrected_key == "startYear":
                query["publication_year"] = query.get("publication_year", {})
                query["publication_year"]["$gte"] = int(value)
            elif corrected_key == "endYear":
                query["publication_year"] = query.get("publication_year", {})
                query["publication_year"]["$lte"] = int(value)
            else:
                # **Diğer filtreler için normal `$regex` kullan**
                if corrected_key in list_fields:
                    query[corrected_key] = {"$regex": f"^{value}$", "$options": "i"}
                else:
                    query[corrected_key] = {"$regex": value.replace("-", " "), "$options": "i"}

    print("### OLUŞTURULAN MongoDB SORGU ###", query)  # **MongoDB'ye giden sorguyu gösterelim**

    # **MongoDB'den `_id` alanını string formatında döndürme**
    results = collection.find(query, {'_id': 1, 'title': 1, 'description': 1, 'link': 1, 'content_format': 1})
    response = []
    for doc in results:
        doc['_id'] = str(doc['_id'])  # `_id` alanını string'e çeviriyoruz
        response.append(doc)

    return jsonify(response)


@app.route('/search', methods=['POST'])
def search():
    data = request.json
    search_query = data.get("query", "").strip()

    results = []

    if search_query:
        results = list(collection.find(
            {
                "$or": [
                    {"title": {"$regex": search_query, "$options": "i"}},
                    {"description": {"$regex": search_query, "$options": "i"}}
                ]
            },
            {"_id": 0}  # `_id` alanını dışarıda bırak
        ))

    return jsonify(results)


@app.route("/api/moderate-text", methods=["POST"])
def moderate_text_api():
    data = request.get_json()
    user_text = data.get("text", "").strip()

    if not user_text:
        return jsonify({"error": "Input text is empty"}), 400

    # 🔥 **GÜÇLENDİRİLMİŞ PROMPT**
    system_message = """
    You are a text moderation AI specializing in correcting hate speech, particularly against women.
    
    **Rules:**
    - If the input contains offensive or discriminatory language, rewrite it in a respectful and inclusive way.
    - If the text is already neutral, return it unchanged.
    - Do NOT return 'undefined' or empty responses.
    - Your correction should preserve the original meaning while making it non-offensive.

    **Examples:**
    - "Women cannot drive cars." → "Driving skills are not determined by gender."
    - "Females should not work in tech." → "Anyone can work in tech, regardless of gender."
    - "Women are weak." → "Women are just as strong and capable as anyone else."
    - "Women can drive." → "Women can drive." (No change needed)

    If the input is already neutral, return it unchanged.
    If the text cannot be corrected meaningfully, provide an educational explanation instead of 'undefined'.
    """

    user_message = f'Input: "{user_text}"\nCorrected Output:'

    try:
        client2 = openai.OpenAI(api_key=OPENAI_API_KEY)

        response = client2.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=100,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )

        print("🔍 OpenAI Response:", response)  # Debugging
        moderated_text = response.choices[0].message.content.strip()

        # 🚨 Check for "undefined"
        if "undefined" in moderated_text.lower():
            moderated_text = "🚫 AI could not generate a valid correction. However, gender does not determine abilities."

        # ✅ Response Formatting
        if moderated_text.lower() == user_text.lower():
            return jsonify({
                "original_text": user_text,
                "moderated_text": "✅ This text looks appropriate: " + user_text
            })
        else:
            return jsonify({
                "original_text": user_text,
                "moderated_text":  moderated_text
            })

    except Exception as e:
        print("❌ Error:", str(e))  # Debugging
        return jsonify({"error": str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    # Dosyanın "uploads" klasöründen sunulmasını sağlar
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# **Yeni Route: Makale Detay Sayfası**
@app.route('/document/<doc_id>')
def document_detail(doc_id):
    try:
        document = collection.find_one({"_id": ObjectId(doc_id)}, {"_id": 0, "title": 1, "description": 1, "link": 1, "content_format": 1})
    except:
        return "Invalid document ID", 400

    if not document:
        return "Document not found", 404

    return render_template('document.html', document=document)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Render provides a dynamic port
    app.run(host="0.0.0.0", port=port, debug=False)

