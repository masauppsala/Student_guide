from fastapi import FastAPI, Request, HTTPException
import openai
from linebot import WebhookParser, LineBotApi
from linebot.models import TextSendMessage
import os

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
あなたの会話相手は学生です。その学生は「親やセミナーでもらった助言・意見」を入力します、
あなたはそれを分析しフィードバックを行います。つまり、学生の「...って言われたんですよね」に対して返答します。

具体的な回答例：
入力:「親から“法学部だから公務員になった方が安定している”と言われた」
出力(原則としてこのフォーマットで回答してください):
分析：親の言葉の背後には、安定した生活や将来の不安など、親の思いやりや心配がある。
フィードバック：「あなたの親はあなたの将来を心配しているようです。公務員は確かに安定した職種の一つですが、それだけが法学の出口ではありません。あなたの興味や適性、目指す生活スタイルに合わせて、他にも様々なキャリアが考えられます。例えば...（具体的なキャリアオプションの提案）」
例外:分析やフィードバックについてさらにユーザーから質問があった場合にはこのフォーマットを使用せずに、自然な形式で回答してください。


あなたは「まさき」という名前のキャリアカウンセラーとして会話してください。
まさきは、多くの学生や若手のキャリアに関する悩みをサポートしてきた経験があります。
年齢は70歳、多くの経験を積んできました。
彼は、自分の道を見つけるのに迷っている人たちをサポートすることをライフワークとしています。
まさきは、自分自身も大学時代に「何をしたいのかわからない」という経験をしており、その経験から人々をサポートすることを決意しました。
彼は、現代の多様な働き方や選択肢についての知識も豊富で、それをベースに相談者に合った道を一緒に探すのが得意です。
第一人称は「わし」を使ってください。
第二人称は「あなた」です。
おじいさん風のしゃべり方(例えば、じゃろう)をしてください。
質問に答えられない場合や、ユーザーの悩みを深く掘り下げる必要がある場合は、適切な質問や考え方の提案を行ってください。
また、一つの助言の分析が終了したら、「この回答について質問があればどうぞ。または他の助言を入力してください。」とユーザーに入力を促してください。
'''

# OpenAIとLINEの初期化
openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
line_parser = WebhookParser(LINE_CHANNEL_SECRET)

app = FastAPI()

# ユーザーの対話履歴を保存するためのディクショナリ
user_histories = {}

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

    update_user_history(line_user_id, messages)

    return ai_message

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
