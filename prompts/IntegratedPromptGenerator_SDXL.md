⚠ 人物に関するワード（肌・髪など）を強調すると構図が寄る（人物が拡大されて写る）。
⚠ 髪の後ろ側の特徴語（ponytail など）は後ろ向き・横向きの構図に寄る。後ろ姿を狙うときは from behind / back view の直接指定＋この型の語で補強、正面顔に戻したいときは looking at viewer を足す。
このファイルがプロンプトの正本。直したら `python3 build_html.py` で画面を作り直す。
⛔ prompt_prefix（Pony のスコアタグ等）はここに書かない——モデルの作法は model_rules.py の担当。

## 既定値
### prompt
- masterpiece, best quality
- RAW photo, dslr, film grain, photorealistic
- detailed skin, skin pores, natural skin texture
### negative
- bad hands, deformed hands, extra fingers, mutated hands
- worst quality, low quality, jpeg artifacts, blurry, watermark
- cartoon, anime

## 被写体
- 1girl, japanese, long hair
- 1girl, japanese, short hair
- 1girl, japanese, ponytail
- mature female, japanese, long hair

## 表情
- (smiling:1.2)
- (gentle smile:1.2)
- (serious expression:1.2)
- (laughing:1.2)

## 服
- (red dress:1.8)
- (blue dress:1.8)
- (white shirt:1.8)
- (black suit:1.8)

## 光
- late afternoon golden light coming from behind her
- soft window light falling on her face from the left
- overcast daylight, even and diffuse light
- warm golden hour sunlight on her face
