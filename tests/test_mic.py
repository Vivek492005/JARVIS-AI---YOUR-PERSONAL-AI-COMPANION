import speech_recognition as sr
import time

def test_microphone():
    r = sr.Recognizer()
    
    # List available microphones
    print("Available microphones:")
    mics = sr.Microphone.list_microphone_names()
    for i, mic in enumerate(mics):
        print(f"{i}: {mic}")
    
    # Use the default microphone
    with sr.Microphone() as source:
        print("\nAdjusting for ambient noise...")
        r.adjust_for_ambient_noise(source, duration=2)
        print(f"Energy threshold set to: {r.energy_threshold:.1f}")
        
        print("\nSpeak now! (say 'hello' or 'test')")
        audio = r.listen(source, timeout=5, phrase_time_limit=5)
        
        try:
            text = r.recognize_google(audio)
            print(f"You said: {text}")
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")

if __name__ == "__main__":
    test_microphone()
