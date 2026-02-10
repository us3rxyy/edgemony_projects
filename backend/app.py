from flask import Flask, request, jsonify
from flask_cors import CORS
from models import db, User, Question, Progress
import json
import os

app = Flask(__name__)
CORS(app)

# Configurazione database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-key-change-in-production'

db.init_app(app)


# Funzione per caricare le domande dai JSON
def load_questions_from_json():
    data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')

    for i in range(1, 7):  # quiz_1.json fino a quiz_6.json
        filename = f'quiz_{i}.json'
        filepath = os.path.join(data_folder, filename)

        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

                # Il JSON ha una struttura con "results"
                questions_list = data.get('results', [])

                for item in questions_list:
                    prompt = item.get('prompt', {})

                    # Estrai la domanda (rimuovendo i tag HTML)
                    question_text = prompt.get('question', '').replace('<p>', '').replace('</p>', '').replace('\n',
                                                                                                              ' ').strip()

                    # Estrai le risposte
                    answers = prompt.get('answers', [])
                    if len(answers) < 4:
                        continue  # Salta se non ci sono 4 risposte

                    # Pulisci le risposte dai tag HTML
                    option_a = answers[0].replace('<p>', '').replace('</p>', '').strip()
                    option_b = answers[1].replace('<p>', '').replace('</p>', '').strip()
                    option_c = answers[2].replace('<p>', '').replace('</p>', '').strip()
                    option_d = answers[3].replace('<p>', '').replace('</p>', '').strip()

                    # Estrai la risposta corretta
                    correct_response = item.get('correct_response', [])
                    if not correct_response:
                        continue

                    # Converti la risposta (a, b, c, d) in maiuscolo (A, B, C, D)
                    correct_answer = correct_response[0].upper()

                    # Controlla se la domanda esiste già
                    existing = Question.query.filter_by(
                        question_text=question_text
                    ).first()

                    if not existing:
                        question = Question(
                            quiz_file=filename,
                            question_text=question_text,
                            option_a=option_a,
                            option_b=option_b,
                            option_c=option_c,
                            option_d=option_d,
                            correct_answer=correct_answer
                        )
                        db.session.add(question)

            db.session.commit()
            print(f"Caricato {filename}")


# Creazione database e caricamento domande
with app.app_context():
    db.create_all()

    # Debug: mostra il percorso
    data_folder = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    print(f"DEBUG - Cerco i file JSON in: {data_folder}")
    print(f"DEBUG - La cartella esiste? {os.path.exists(data_folder)}")

    if os.path.exists(data_folder):
        print(f"DEBUG - File nella cartella: {os.listdir(data_folder)}")

    # Carica le domande solo se il database è vuoto
    if Question.query.count() == 0:
        load_questions_from_json()
        print(f"DEBUG - Domande totali caricate: {Question.query.count()}")
    else:
        print(f"DEBUG - Database già popolato con {Question.query.count()} domande")

#API endpoint, registrazione utente
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username già esistente'}), 400

    new_user = User(username=username, password=password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'Registrazione completata', 'user_id': new_user.id}), 201
#login
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username, password=password).first()

    if user:
        return jsonify({'message': 'Login effettuato', 'user_id': user.id, 'username': user.username}), 200
    else:
        return jsonify({'error': 'Credenziali non valide'}), 401

#domande x un quiz specifico
@app.route('/api/quiz/<int:quiz_number>', methods=['GET'])
def get_quiz(quiz_number):
    filename = f'quiz_{quiz_number}.json'
    questions = Question.query.filter_by(quiz_file=filename).all()

    quiz_data = []
    for q in questions:
        quiz_data.append({
            'id': q.id,
            'domanda': q.question_text,
            'risposte': {
                'A': q.option_a,
                'B': q.option_b,
                'C': q.option_c,
                'D': q.option_d
            }
        })

    return jsonify(quiz_data), 200

#salva le risposte
@app.route('/api/answer', methods=['POST'])
def save_answer():
    data = request.json
    user_id = data.get('user_id')
    question_id = data.get('question_id')
    user_answer = data.get('answer')

    question = Question.query.get(question_id)
    is_correct = (user_answer == question.correct_answer)

    progress = Progress(
        user_id=user_id,
        question_id=question_id,
        user_answer=user_answer,
        is_correct=is_correct
    )
    db.session.add(progress)
    db.session.commit()

    return jsonify({
        'correct': is_correct,
        'correct_answer': question.correct_answer
    }), 200


# Ottenere statistiche utente
@app.route('/api/stats/<int:user_id>', methods=['GET'])
def get_stats(user_id):
    progresses = Progress.query.filter_by(user_id=user_id).all()

    total = len(progresses)
    correct = sum(1 for p in progresses if p.is_correct)
    wrong = total - correct

    percentage = (correct / total * 100) if total > 0 else 0

    return jsonify({
        'total_questions': total,
        'correct_answers': correct,
        'wrong_answers': wrong,
        'percentage': round(percentage, 2)
    }), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)