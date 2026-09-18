import speech_recognition as sr
import time

def test_voice_recognition():
    # Initialize recognizer
    r = sr.Recognizer()
    
    # Use the default microphone
    with sr.Microphone() as source:
        print("\nAdjusting for ambient noise... (please wait)")
        r.adjust_for_ambient_noise(source, duration=2)
        print(f"Energy threshold set to: {r.energy_threshold:.1f}")
        
        print("\nSpeak now! (say 'hello' or 'test')")
        print("Listening for 5 seconds...")
        
        try:
            # Listen for 5 seconds
            audio = r.listen(source, timeout=5, phrase_time_limit=5)
            
            # Try to recognize the speech
            print("Processing...")
            text = r.recognize_google(audio)
            print(f"You said: {text}")
            
            # Check for wake word
            if "access" in text.lower():
                print("Wake word detected!")
                
        except sr.WaitTimeoutError:
            print("No speech detected. Try speaking louder.")
        except sr.UnknownValueError:
            print("Could not understand audio")
        except sr.RequestError as e:
            print(f"Could not request results; {e}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    print("Voice Recognition Test")
    print("=====================")
    
    while True:
        test_voice_recognition()
        
        # Ask if user wants to try again
        again = input("\nTest again? (y/n): ").lower()
        if again != 'y':
            break
