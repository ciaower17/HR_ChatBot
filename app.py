from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import anthropic
import os
import json
import datetime

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "uploads"
HISTORY_FILE = "chat_history.json"
CONTACT_FALLBACK = "Non ho trovato informazioni su questo argomento nei documenti aziendali. Per assistenza contatta l'amministrazione al numero 02 1234567 oppure scrivi a hr@azienda.it"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def load_documents():
    docs_text = ""
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if filename.endswith(".txt"):
            with open(filepath, "r", encoding="utf-8") as f:
                docs_text += f"\n\n--- DOCUMENTO: {filename} ---\n" + f.read()
        elif filename.endswith(".pdf"):
            try:
                import PyPDF2
                with open(filepath, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    docs_text += f"\n\n--- DOCUMENTO: {filename} ---\n"
                    for page in reader.pages:
                        docs_text += page.extract_text() or ""
            except Exception as e:
                docs_text += f"\n\n--- DOCUMENTO: {filename} (errore: {e}) ---\n"
    return docs_text.strip()

def save_history(user_msg, bot_msg):
    history = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append({"timestamp": datetime.datetime.now().isoformat(), "user": user_msg, "bot": bot_msg})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@app.route("/")
def index():
    return render_template("chat.html")

@app.route("/admin")
def admin():
    return render_template("admin.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Messaggio vuoto"}), 400
    docs_text = load_documents()
    if docs_text:
        system_prompt = f"""Sei un assistente virtuale interno per i dipendenti dell'azienda.
Rispondi SOLO basandoti sui documenti aziendali forniti qui sotto.
Se la risposta non è presente nei documenti, rispondi ESATTAMENTE con questo testo senza aggiungere nulla:
"{CONTACT_FALLBACK}"
Non inventare informazioni. Sii chiaro, conciso e professionale. Rispondi sempre in italiano.

DOCUMENTI AZIENDALI:
{docs_text}"""
    else:
        system_prompt = f"""Sei un assistente virtuale interno per i dipendenti dell'azienda.
Al momento non sono stati caricati documenti aziendali.
Per qualsiasi domanda rispondi ESATTAMENTE con questo testo:
"{CONTACT_FALLBACK}"
Rispondi sempre in italiano."""
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )
    bot_reply = response.content[0].text
    save_history(user_message, bot_reply)
    return jsonify({"reply": bot_reply})

@app.route("/api/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "Nessun file inviato"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nome file vuoto"}), 400
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in {".txt", ".pdf"}:
        return jsonify({"error": "Formato non supportato. Usa TXT o PDF."}), 400
    file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return jsonify({"message": f"File '{file.filename}' caricato con successo."})

@app.route("/api/documents", methods=["GET"])
def list_documents():
    files = []
    for filename in os.listdir(UPLOAD_FOLDER):
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        size = os.path.getsize(filepath)
        modified = datetime.datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%d/%m/%Y %H:%M")
        files.append({"name": filename, "size": size, "modified": modified})
    return jsonify({"documents": files})

@app.route("/api/documents/<filename>", methods=["DELETE"])
def delete_document(filename):
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File non trovato"}), 404
    os.remove(filepath)
    return jsonify({"message": f"File '{filename}' eliminato."})

@app.route("/api/history", methods=["GET"])
def history():
    return jsonify({"history": load_history()})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
