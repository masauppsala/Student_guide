from fastapi import FastAPI, Request, HTTPException
import openai
from linebot import WebhookParser, LineBotApi
from linebot.models import TextSendMessage
import os
import random

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise ValueError("API key is not set!")

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
if not LINE_CHANNEL_ACCESS_TOKEN:
    raise ValueError("LINE_CHANNEL_ACCESS_TOKEN is not set!")

LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')
if not LINE_CHANNEL_SECRET:
    raise ValueError("LINE_CHANNEL_SECRET is not set!")

OPENAI_CHARACTER_PROFILE = '''
あなたは「まさき」という名前の70歳のキャリアカウンセラーです。学生時代に自らも「何をしたいのかわからない」という経験を持ち、その後、多くの学生や若手のキャリアに関する悩みをサポートしてきました。彼のライフワークは、迷っている人たちのキャリアをサポートすること。まさきは現代の多様な働き方や選択肢に詳しく、相談者のニーズに応じてアドバイスをします。

会話のスタイルはおじいさん風。分析やフィードバックの時もおじいさん風に話してください。第一人称は「わし」、第二人称は「あなた」を使用。学生からの助言・意見について、以下のフォーマットで返答：
分析：[まさきの考察]
フィードバック：[具体的なアドバイス]

ただし、ユーザーからの質問や深く掘り下げが必要な場合は、このフォーマットを外れても良い。

一つの助言の分析が終了したら、ユーザーに次のアクションを促します：
「この回答についての質問があればどうぞ。または他の助言を入力してください。」
'''

# OpenAIとLINEの初期化
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
line_parser = WebhookParser(LINE_CHANNEL_SECRET)

app = FastAPI()

# ユーザーの対話履歴を保存するためのディクショナリ
user_histories = {}

KOTOBAZU = [
    "昔の言い伝えには、'石の上にも三年'と言うじゃろう。辛抱強く続けることが大切じゃ。",
    "昔から言うじゃろう、'七転び八起き'。失敗は成功の元じゃ。",
    "わしの時代にはよく言ったもんじゃ、'果報は寝て待て'。焦らず、時を待つことも大切じゃよ。"
]

@app.post('/')
async def ai_talk(request: Request):
    signature = request.headers.get('X-Line-Signature', '')
    body = (await request.body()).decode('utf-8')

    try:
        events = line_parser.parse(body, signature)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    for event in events:
        if event.type == 'message' and event.message.type == 'text':
            response_message = process_line_event(event)
            line_bot_api.push_message(event.source.user_id, TextSendMessage(response_message))

    return 'ok'

def process_line_event(event):
    line_user_id = event.source.user_id
    line_message = event.message.text

    messages = build_openai_messages(line_user_id, line_message)
    
    try:
        ai_message = get_openai_response(messages)

    except Exception as e:
        return f"エラー: {str(e)}"

    ai_message = interpret_emoji(ai_message)  # 絵文字を解釈
    ai_message = insert_kotobazu(ai_message)  # ことわざや古い話を挟む
    
    update_user_history(line_user_id, messages)

    return ai_message

def interpret_emoji(message):
    # サンプルとして、絵文字の一部を解釈して返答を加工する
    if "😀" in message:
        return message + " あなたは楽しそうにしているね。"
    elif "😢" in message:
        return message + " 何か悲しいことがあったのか？"
    else:
        return message

def insert_kotobazu(message):
    # ある確率でことわざや古い話を返答に挟む
    if random.random() < 0.2:  # 20%の確率でことわざを挟む
        message += " " + random.choice(KOTOBAZU)
    return message

def build_openai_messages(line_user_id, line_message):
    # 共通のキャラクタープロフィール
    system_message = {
        'role': 'system',
        'content': OPENAI_CHARACTER_PROFILE.strip()
    }
    
    # ユーザー履歴の取得・更新
    messages = [system_message]
    if line_user_id in user_histories:
        messages.extend(user_histories[line_user_id])

    messages.append({
        'role': 'user',
        'content': line_message
    })

    return messages

def get_openai_response(messages):
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        temperature=0.5,
        messages=messages
    )
    return response['choices'][0]['message']['content']

def update_user_history(line_user_id, messages):
    if len(messages) > 5:  # 一定数を超えたら古いメッセージを削除
        messages.pop(1)
    user_histories[line_user_id] = messages[1:]
