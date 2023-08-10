from fastapi import FastAPI, Request
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


あなたは「セイ」という名前のキャリアカウンセラーとして会話してください。
セイは、多くの学生や若手のキャリアに関する悩みをサポートしてきた経験があります。
年齢は30歳。若いが、短期間で多くの経験を積んできました。
彼は、自分の道を見つけるのに迷っている人たちをサポートすることをライフワークとしています。
セイは、自分自身も大学時代に「何をしたいのかわからない」という経験をしており、その経験から人々をサポートすることを決意しました。
彼は、現代の多様な働き方や選択肢についての知識も豊富で、それをベースに相談者に合った道を一緒に探すのが得意です。
第一人称は「僕」を使ってください。
第二人称は「あなた」です。
質問に答えられない場合や、ユーザーの悩みを深く掘り下げる必要がある場合は、適切な質問や考え方の提案を行ってください。
また、一つの助言の分析が終了したら、「他の助言を入力してください」とユーザーに促してください。
'''

openai.api_key = OPENAI_API_KEY
line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
line_parser = WebhookParser(LINE_CHANNEL_SECRET)
app = FastAPI()


@app.post('/')
async def ai_talk(request: Request):
    # X-Line-Signature ヘッダーの値を取得
    signature = request.headers.get('X-Line-Signature', '')

    # request body から event オブジェクトを取得
    events = line_parser.parse((await request.body()).decode('utf-8'), signature)

    # 各イベントの処理（※1つの Webhook に複数の Webhook イベントオブジェっｚクトが含まれる場合あるため）
    for event in events:
        if event.type != 'message':
            continue
        if event.message.type != 'text':
            continue

        # LINE パラメータの取得
        line_user_id = event.source.user_id
        line_message = event.message.text

        # ChatGPT からトークデータを取得
        response = openai.ChatCompletion.create(
            model = 'gpt-3.5-turbo'
            , temperature = 0.5
            , messages = [
                {
                    'role': 'system'
                    , 'content': OPENAI_CHARACTER_PROFILE.strip()
                }
                , {
                    'role': 'user'
                    , 'content': line_message
                }
            ]
        )
        ai_message = response['choices'][0]['message']['content']

        # LINE メッセージの送信
        line_bot_api.push_message(line_user_id, TextSendMessage(ai_message))

    # LINE Webhook サーバーへ HTTP レスポンスを返す
    return 'ok'
