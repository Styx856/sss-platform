from babel.messages.mofile import write_mo
from babel.messages.pofile import read_po
import os

def compile_translations():
    translations_dir = os.path.join(os.path.dirname(__file__), 'translations')
    for lang in ['en']:  # Add more languages if needed
        po_file = os.path.join(translations_dir, lang, 'LC_MESSAGES', 'messages.po')
        mo_file = os.path.join(translations_dir, lang, 'LC_MESSAGES', 'messages.mo')
        
        with open(po_file, 'rb') as po_input:
            catalog = read_po(po_input)
        
        with open(mo_file, 'wb') as mo_output:
            write_mo(mo_output, catalog)

if __name__ == '__main__':
    compile_translations()
    print("Translations compiled successfully!")
