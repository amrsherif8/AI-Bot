from gtts import gTTS

def text_to_speech(text, lang='de', slow=False, output_file="output.mp3"):
    tts = gTTS(text=text, lang=lang, slow=slow)
    tts.save(output_file)
    return f"Saved speech to {output_file}"

if __name__ == "__main__":
    user_text = input("Enter the text: ")
    if user_text.strip():
        result = text_to_speech(user_text, lang='de', output_file="Sound_1.mp3")
        print(result)




# 
# py -m edge_tts --voice de-AT-JonasNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3
# py -m edge_tts --voice de-CH-JanNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3
# py -m edge_tts --voice de-CH-LeniNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3
# py -m edge_tts --voice de-DE-AmalaNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3
# py -m edge_tts --voice de-DE-ConradNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3
# py -m edge_tts --voice de-DE-FlorianMultilingualNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3
# py -m edge_tts --voice de-DE-KatjaNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3
# py -m edge_tts --voice de-DE-KillianNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3
# py -m edge_tts --voice de-DE-SeraphinaMultilingualNeural  --text "Ich bin der Albtraum, der in der Dunkelheit auf euch wartet... Ich werde eure Seelen verschlingen und eure Tage zur Hölle machen... Es gibt kein Entkommen, euer Ende ist unausweichlich" --write-media test.mp3