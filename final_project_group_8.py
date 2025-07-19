from collections import UserDict
from datetime import datetime, timedelta
import pickle
import os
import re
from rich.console import Console
from rich.table import Table
from rich.text import Text
import difflib

console = Console()

def show_all_rich(book):
    if not book:
        console.print("😓 Address book is empty.", style="yellow")
        return

    table = Table(title="📒 Address Book", show_lines=True)
    table.add_column("Name", style="bold magenta")
    table.add_column("Phones", style="green")
    table.add_column("Birthday", style="cyan")
    table.add_column("Email", style="blue")
    table.add_column("Address", style="white")
    table.add_column("Notes", style="yellow")

    for record in book.values():
        phones = ", ".join(phone.value for phone in record.phones) if record.phones else "-"
        birthday = record.birthday.value if record.birthday else "-"
        email = record.email.value if record.email else "-"
        address = record.address.value if record.address else "-"

        notes_block = Text("-")
        if record.notes:
            notes_block = Text()
            for note in record.notes:
                note_text = Text(note.text, style="bold yellow")
                tags_text = Text(" " + " ".join(f"#{tag}" for tag in note.tags), style="dim") if note.tags else Text("")
                notes_block.append_text(note_text)
                notes_block.append_text(tags_text)
                notes_block.append("\n")

        table.add_row(
            record.name.value,
            phones,
            birthday,
            email,
            address,
            notes_block
        )

    console.print(table)
    return ""

DEFAULT_FILENAME = "address_book.pkl"

class Field:
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return str(self.value)

class Name(Field):
    pass

class Phone(Field):
    VALID_CODES = ["050", "066", "067", "068", "095", "096", "097", "098", "099", "063", "073", "093"]

    def __init__(self, value):
        if not value.isdigit() or len(value) != 10:
            raise ValueError("😓 Phone number must contain exactly 10 digits.")
        if not any(value.startswith(code) for code in self.VALID_CODES):
            raise ValueError(f"😓 The phone number must start with a valid code: {', '.join(self.VALID_CODES)}.")
        super().__init__(value)

class Birthday(Field):
    def __init__(self, value):
        try:
            birthday_date = datetime.strptime(value, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("😓 Invalid date format. Use DD.MM.YYYY")
        if birthday_date > datetime.today().date():
            raise ValueError("😓 Birthday cannot be in the future.")
        if birthday_date.year < 1930:
            raise ValueError("😓 Unrealistic birthday. Please try again.")
        super().__init__(value)

class Address(Field):
    pass

class Email(Field):
    def __init__(self, value):
        if not self.validate_email(value):
            raise ValueError("😓 Invalid email format. Please use name@example.com")
        super().__init__(value)

    @staticmethod
    def validate_email(value):
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return re.match(pattern, value) is not None

class Note(Field):
    
    TAG_PATTERN = re.compile(r"^[a-zA-Z0-9_]{1,30}$")
    
    def __init__(self, text, tags=None):
        self.text = text.strip()
        self.tags = set()
        for tag in (tags or []):
            self.add_tag(tag)

    def add_tag(self, tag):
        tag_clean = tag.lstrip("#").lower()
        if not self.TAG_PATTERN.fullmatch(tag_clean):
            raise ValueError(f"😓 Invalid tag: '{tag}'. Only letters, digits, and underscores are allowed (1–30 chars).")
        self.tags.add(tag_clean)

    def remove_tag(self, tag):
        self.tags.discard(tag.lstrip("#").lower())

    def has_tag(self, tag):
        return tag.lstrip("#").lower() in self.tags

    def __str__(self):
        tag_str = f" [#{', #'.join(sorted(self.tags))}]" if self.tags else ""
        return f"{self.text}{tag_str}"

    def __eq__(self, other):
        return isinstance(other, Note) and self.text == other.text and self.tags == other.tags


class Record:
    def __init__(self, name):
        self.name = Name(name)
        self.phones = []
        self.birthday = None
        self.address = None
        self.email = None
        self.notes = []
    

    def add_phone(self, phone, book):
        try:
            phone_obj = Phone(phone)
        except ValueError as e:
            return str(e)
        if any(p.value == phone for p in self.phones):
            return f"😓 The number '{phone}' already exists for this contact."
        for record in book.data.values():
            if record != self and any(p.value == phone for p in record.phones):
                return f"😓 The number '{phone}' already belongs to '{record.name.value}'."
        self.phones.append(phone_obj)
        return None

    def remove_phone(self, phone):
        phone_obj = self.find_phone(phone)
        if phone_obj:
            self.phones.remove(phone_obj)
            return True
        return False

    def edit_phone(self, old_phone, new_phone, book):
        if not self.find_phone(old_phone):
            return f"😓 The old number '{old_phone}' was not found."
        try:
            new_phone_obj = Phone(new_phone)
        except ValueError as e:
            return str(e)
        for record in book.data.values():
            if record != self and any(p.value == new_phone for p in record.phones):
                return f"😓 The new number '{new_phone}' already belongs to '{record.name.value}'."
        for i, phone in enumerate(self.phones):
            if phone.value == old_phone:
                self.phones[i] = new_phone_obj
                return None
        return "😓 Something went wrong while updating the number."

    def find_phone(self, phone):
        for p in self.phones:
            if p.value == phone:
                return p
        return None

    def add_birthday(self, birthday_str):
        self.birthday = Birthday(birthday_str)

    def edit_birthday(self, new_birthday):
        self.birthday = Birthday(new_birthday)

    def remove_birthday(self):
        self.birthday = None

    def add_address(self, address):
        self.address = Address(address)

    def edit_address(self, new_address):
        if self.address:
            self.address.value = new_address
        else:
            self.add_address(new_address)

    def remove_address(self):
        self.address = None

    def add_email(self, email):
        self.email = Email(email)

    def edit_email(self, new_email):
        if self.email:
            try:
                self.email = Email(new_email)
            except ValueError as e:
                return str(e)
        else:
            return "😓 Email is not set. Use 'addemail' to add one."

    def remove_email(self):
        self.email = None

    def add_note(self, text, tags=None):
        new_note = Note(text, tags)

        for existing_note in self.notes:
            if existing_note.text.strip().lower() == new_note.text.strip().lower():
                return None

        self.notes.append(new_note)
        return new_note

    def remove_note(self, text):
        normalized_input = re.sub(r"#\w+", "", text).strip().lower()
        for note in self.notes:
            if note.text.strip().lower() == normalized_input:
                self.notes.remove(note)
                return "✅ Note removed!"
        return "😓 Note not found."

    def edit_note(self, old_text, new_text):
        normalized_old = old_text.strip().lower()
        cleaned_new_text = re.sub(r"#\w+", "", new_text).strip()
        new_tags = re.findall(r"#(\w+)", new_text)

        for i, note in enumerate(self.notes):
            if note.text.strip().lower() == normalized_old:
                self.notes[i] = Note(cleaned_new_text, new_tags)
                return "✅ Note edited!"
        return "😓 Note not found."
    
    def get_notes_by_tag(self, tag):
        return [note for note in self.notes if note.has_tag(tag)]

    def __str__(self):
        phones_str = "; ".join(str(p) for p in self.phones) if self.phones else "No phone numbers available."
        birthday_str = f", Birthday: {self.birthday}" if self.birthday else ""
        address_str = f", Address: {self.address}" if self.address else ""
        email_str = f", Email: {self.email}" if self.email else ""
        notes_str = f", Notes: {'; '.join(str(note) for note in self.notes)}" if self.notes else ""
        return f"👤 {self.name.value}: {phones_str}{birthday_str}{email_str}{address_str}{notes_str}"

class AddressBook(UserDict):
    def add_record(self, record):
        self.data[record.name.value] = record

    def find(self, name):
        name = name.lower()
        for key, record in self.data.items():
            if key.lower() == name:
                return record
        return None

    def name_exists(self, name):
        return any(name.lower() == key.lower() for key in self.data)

    def delete(self, name):
        for key in list(self.data):
            if key.lower() == name.lower():
                del self.data[key]
                return True
        return False

    def search(self, query):
        result = []
        query = query.lower()
        for record in self.data.values():
            name_match = query in record.name.value.lower()
            phone_match = any(query in phone.value for phone in record.phones)
            email_match = record.email and query in record.email.value.lower()
            address_match = record.address and query in record.address.value.lower()
            birthday_match = record.birthday and query in record.birthday.value.lower()
            if name_match or phone_match or email_match or address_match or birthday_match:
                result.append(str(record))
        return result

    def get_upcoming_birthdays(self, days=7):
        today = datetime.today().date()
        end_date = today + timedelta(days=days)
        upcoming = []
        for record in self.data.values():
            if not record.birthday:
                continue
            try:
                birthday_date = datetime.strptime(record.birthday.value, "%d.%m.%Y").date()
                birthday_this_year = birthday_date.replace(year=today.year)
                if birthday_this_year < today:
                    birthday_this_year = birthday_this_year.replace(year=today.year + 1)
                if today <= birthday_this_year <= end_date:
                    congratulation_date = birthday_this_year
                    if congratulation_date.weekday() == 5:
                        congratulation_date += timedelta(days=2)
                    elif congratulation_date.weekday() == 6:
                        congratulation_date += timedelta(days=1)
                    upcoming.append(f"{record.name.value}: {congratulation_date.strftime('%d.%m.%Y')}")
            except ValueError:
                continue
        return upcoming

def save_address_book(book, filename=DEFAULT_FILENAME):
    try:
        with open(filename, "wb") as file:
            pickle.dump(book, file)
    except Exception as e:
        console.print(f"😓 Error saving address book to '{filename}': {e}", style="red")

def load_address_book(filename=DEFAULT_FILENAME):
    if os.path.exists(filename):
        try:
            with open(filename, "rb") as file:
                book = pickle.load(file)
                for record in book.values():
                    if not hasattr(record, "address"):
                        record.address = None
                    if not hasattr(record, "email"):
                        record.email = None
                    if not hasattr(record, "notes"):
                        record.notes = []
                return book
        except Exception as e:
            console.print(f"😓 Error loading address book from '{filename}': {e}", style="red")
            console.print("Creating a new empty address book instead.", style="yellow")
            return AddressBook()
    return AddressBook()

def parse_input(user_input):
    cmd, *args = user_input.strip().split()
    return cmd.strip().lower(), args

def normalize_name(name):
    def fix_part(part):
        return "-".join(subpart.capitalize() for subpart in part.split("-"))
    return " ".join(fix_part(word) for word in name.strip().split())

def format_address(address: str) -> str:
    parts = address.split()
    formatted = []

    for word in parts:
        if word.lower().endswith('.') and len(word) <= 4:
            formatted.append(word.lower())
        else:
            formatted.append(word.capitalize())

    return " ".join(formatted)

def suggest_command(input_cmd, valid_commands):
    prefix_matches = [cmd for cmd in valid_commands if cmd.startswith(input_cmd)]

    if prefix_matches:
        return f"🤔 Did you mean one of these commands: {', '.join(f'\'{cmd}\'' for cmd in prefix_matches)}? Please try again!"

    fuzzy_matches = difflib.get_close_matches(input_cmd, valid_commands, n=5, cutoff=0.6)

    if fuzzy_matches:
        if len(fuzzy_matches) == 1:
            return f"🤔 Did you mean '{fuzzy_matches[0]}'? Please try again!"
        else:
            return f"🤔 Did you mean one of these commands: {', '.join(f'\'{cmd}\'' for cmd in fuzzy_matches)}? Please try again!"

    return "😓 Sorry, that command doesn’t exist. Type 'help' to see available commands."

def extract_tags_from_text(text):
    return [tag[1:].lower() for tag in re.findall(r"#\w+", text)]

def input_error(func):
    error_messages = {
        "addcontact": (
    "😓 The 'addcontact' command requires at least a name and a 10-digit phone number.\n"
    "👉 You can also optionally add more phone numbers, an email and an address.\n"
    "🔹 Examples:\n"
    "   'addcontact Ivan 0987654321'\n"
    "   'addcontact Ivan Petrov 0981112222 0663334444'\n"
    "   'addcontact Ivan 0987654321 ivan@example.com'\n"
    "   'addcontact Ivan 0987654321 ivan@gmail.com vul. Parkova 12, Kyiv'\n"
),
        "editname": "😓 The 'editname' command requires the old and new name. For example: 'editname Ivan Petro'",
        "removecontact": "😓 The 'removecontact' command requires a name. For example: 'removecontact Ivan'",
        "addphone": "😓 The 'addphone' command requires a name and a phone number. For example: 'addphone Ivan 0661234567'",
        "changephone": "😓 The 'changephone' command requires a name, the old number and the new number. For example: 'changephone Ivan 0661234567 0961234567'",
        "removephone": "😓 The 'removephone' command requires a name and a phone number to remove. For example: 'removephone Ivan 0661234567'",
        "showphone": "😓 The 'showphone' command requires only a name. For example: 'showphone Ivan'",
        "addbday": "😓 The 'addbday' command requires a name and a date (DD.MM.YYYY). For example: 'addbday Ivan 15.05.1990'",
        "showbday": "😓 The 'showbday' command requires only a name. For example: 'showbday Ivan'",
        "editbday": "😓 The 'editbday' command requires a name and a new date (DD.MM.YYYY). For example: 'editbday Ivan 16.05.1990'",
        "removebday": "😓 The 'removebday' command requires a name. For example: 'removebday Ivan'",
        "upcomingbdays": "😓 The 'upcomingbdays' command doesn’t require any arguments. Just type 'upcomingbdays'.",
        "search": "😓 The 'search' command requires a query like name, phone, birthday, email or address. For example: 'search Ivan' or 'search 0661234567' or search '15.05.1990' or search 'ivan@example.com' or search 'vul. 3, Kyiv'",
        "all": "😓 The 'all' command doesn’t require any arguments. Just type 'all'.",
        "addemail": "😓 The 'addemail' command requires a name and an email. For example: 'addemail Ivan ivan@example.com'",
        "editemail": "😓 The 'editemail' command requires a name and a new email. For example: 'editemail Ivan new@example.com'",
        "removeemail": "😓 The 'removeemail' command requires a name. For example: 'removeemail Ivan'",
        "addaddress": "😓 The 'addaddress' command requires a name and an address. For example: 'addaddress Ivan vul. Vilna 1, Kyiv'",
        "editaddress": "😓 The 'editaddress' command requires a name and a new address. For example: 'editaddress Ivan vul. New 2, Kyiv'",
        "removeaddress": "😓 The 'removeaddress' command requires a name. For example: 'removeaddress Ivan'",
        "addnote": "😓 The 'addnote' command requires a name and a note text. You can optionally include tags using #. For example: 'addnote Ivan Meeting at 3:00 PM #urgent'",
        "editnote": "😓 The 'editnote' command requires a name, the old note and the new note. You can also include tags. For example: 'editnote Ivan Meeting at 3:00 PM Meeting rescheduled to 4:00 PM #urgent'",
        "removenote": (
    "😓 The 'removenote' command requires a name and optionally the note text.\n"
    "🔹 Example 1 (remove specific note): 'removenote Ivan Meeting at 3:00 PM'\n"
    "🔹 Example 2 (remove all notes): 'removenote Ivan'"
),
        "searchnote": "😓 The 'searchnote' command requires a keyword query. For example: 'searchnote Meeting'",
        "searchtag": "😓 The 'searchtag' command requires a tag. For example: 'searchtag #urgent'",
        "addtag": "😓 The 'addtag' command requires a name, the note text and the tag. For example: 'addtag Ivan Project planning #meeting'",
        "removetag": (
    "😓 The 'removetag' command requires a name, the note text and a tag to remove.\n"
    "🔹 Example 1 (remove specific tag): 'removetag Ivan Meeting at 3:00 PM #urgent'\n"
    "🔹 Example 2 (remove all tags from note): 'removetag Ivan Meeting at 3:00 PM'"
),
        "default": "😓 Invalid command or arguments. Type 'help' to see available commands."
    }

    def inner(*args, **kwargs):
        command = kwargs.get('command', 'default')
        try:
            result = func(*args, **kwargs)
            return result
        except ValueError as e:
            return str(e) or error_messages.get(command, error_messages["default"])
        except KeyError:
            return "😓 Contact not found."
        except IndexError:
            return error_messages.get(command, error_messages["default"])
        except Exception as e:
            return f"😓 Something went wrong: {str(e)}"
    return inner

@input_error
def add_contact(args, book, command="addcontact"):
    if len(args) < 2:
        raise IndexError("😓 You must provide at least a name and one valid 10-digit phone number.")

    phone_start_index = None
    for i, arg in enumerate(args):
        if arg.isdigit() and len(arg) == 10:
            phone_start_index = i
            break

    if phone_start_index is None:
        raise ValueError("😓 At least one valid phone number is required (10 digits).")

    name_parts = args[:phone_start_index]
    if not name_parts:
        raise ValueError("😓 Name is missing.")
    name = normalize_name(" ".join(name_parts))
    if book.name_exists(name):
        return f"😓 A contact named '{name}' already exists."

    phones = []
    i = phone_start_index
    while i < len(args) and args[i].isdigit() and len(args[i]) == 10:
        phones.append(args[i])
        i += 1

    record = Record(name)
    for phone in phones:
        result = record.add_phone(phone, book)
        if result:
            return result

    email = None
    address_parts = []

    while i < len(args):
        arg = args[i]
        if "@" in arg:
            email = arg
        else:
            address_parts.append(arg)
        i += 1

    if email:
        record.add_email(email.strip())
    if address_parts:
        raw_address = " ".join(address_parts).strip()
        formatted_address = format_address(raw_address)
        record.add_address(formatted_address)

    book.add_record(record)
    return "✅ Contact added!"

@input_error
def edit_contact_name(args, book, command="editname"):
    if len(args) < 2:
        raise IndexError
    for i in range(1, len(args)):
        old_name_try = normalize_name(" ".join(args[:i]))
        if book.name_exists(old_name_try):
            old_name = old_name_try
            new_name = normalize_name(" ".join(args[i:]))
            break
    else:
        raise KeyError
    record = book.find(old_name)
    book.delete(old_name)
    record.name = Name(new_name)
    book.add_record(record)
    return f"✅ Contact name changed to '{new_name}'!"

@input_error
def change_contact(args, book, command="changephone"):
    if len(args) < 3:
        raise IndexError
    old_phone = args[-2]
    new_phone = args[-1]
    name = normalize_name(" ".join(args[:-2]))
    record = book.find(name)
    if not record:
        raise KeyError
    result = record.edit_phone(old_phone, new_phone, book)
    if result:
        return result
    return "✅ Phone number updated!"

@input_error
def add_phone_to_contact(args, book, command="addphone"):
    if len(args) < 2:
        raise IndexError
    possible_phone = args[-1]
    name = normalize_name(" ".join(args[:-1]))
    record = book.find(name)
    if not record:
        raise KeyError
    result = record.add_phone(possible_phone, book)
    if result:
        return result
    return "✅ Phone number added!"

@input_error
def remove_phone(args, book, command="removephone"):
    if len(args) < 2:
        raise IndexError
    possible_phone = args[-1]
    name = normalize_name(" ".join(args[:-1]))
    record = book.find(name)
    if not record:
        raise KeyError
    if not record.remove_phone(possible_phone):
        return f"😓 Phone number '{possible_phone}' not found."
    return "✅ Phone number removed!"

@input_error
def remove_contact(args, book, command="removecontact"):
    if not args:
        raise IndexError
    name = normalize_name(" ".join(args))
    if not book.delete(name):
        raise KeyError
    return f"✅ Contact '{name}' removed!"

@input_error
def add_birthday(args, book, command="addbday"):
    if len(args) < 2:
        raise IndexError
    name = normalize_name(" ".join(args[:-1]))
    birthday = args[-1]
    try:
        datetime.strptime(birthday, "%d.%m.%Y")
    except ValueError:
        return "😓 Invalid date format. Use DD.MM.YYYY, for example, 15.05.1990."
    record = book.find(name)
    if not record:
        raise KeyError
    if record.birthday:
        return "😓 Birthday is already set. Use ‘editbday’ to change it."
    record.add_birthday(birthday)
    return "🎉 Birthday added!"

@input_error
def show_birthday(args, book, command="showbday"):
    if not args:
        raise IndexError
    name = normalize_name(" ".join(args))
    matches = [record for key, record in book.data.items() if name.lower() in key.lower()]
    if not matches:
        raise KeyError
    if len(matches) == 1:
        record = matches[0]
        if record.birthday:
            return f"🎂 Birthday {record.name.value}: {record.birthday.value}"
        else:
            return "😓 Birthday is not set."
    matches_with_birthday = [r for r in matches if r.birthday]
    if not matches_with_birthday:
        return "😓 None of the contacts have a birthday set."
    result = ["Multiple contacts found:"]
    result += [f"{record.name.value}: {record.birthday.value}" for record in matches]
    result.append("Please provide the full name for an exact match.")
    return "\n".join(result)

@input_error
def edit_birthday(args, book, command="editbday"):
    if len(args) < 2:
        raise IndexError
    name = normalize_name(" ".join(args[:-1]))
    birthday = args[-1]
    record = book.find(name)
    if not record:
        raise KeyError
    record.edit_birthday(birthday)
    return "✅ Birthday updated!"

@input_error
def remove_birthday(args, book, command="removebday"):
    if not args:
        raise IndexError
    name = normalize_name(" ".join(args))
    record = book.find(name)
    if not record:
        raise KeyError
    record.remove_birthday()
    return "✅ Birthday removed!"

@input_error
def show_phone(args, book, command="showphone"):
    if not args:
        raise IndexError
    name = normalize_name(" ".join(args))
    matches = [record for key, record in book.data.items() if name.lower() in key.lower()]
    if not matches:
        raise KeyError
    if len(matches) == 1:
        record = matches[0]
        return f"{record.name.value}: {', '.join(p.value for p in record.phones)}"

    result = ["Multiple contacts found:"]
    result += [f"{r.name.value}: {', '.join(p.value for p in r.phones)}" for r in matches]
    return "\n".join(result)

@input_error
def search_contacts(args, book, command="search"):
    if not args:
        raise IndexError
    query = args[0].lower()
    if query in ["note", "notes"]:
        return "To search notes, use: searchnote <keyword>"
    if query in ["email"]:
        return "Try searching with a correct email or part of it (e.g., gmail)."
    if query in ["address"]:
        return "Try searching with a keyword from the address."
    if query in ["birthday", "bday", "birth"]:
        return "Use a real date, such as 03.11.1991, or part of it."
    results = book.search(query)
    return "\n".join(results) if results else "😓 No matches found."

@input_error
def upcoming_birthdays(args, book, command="upcomingbdays"):
    if args:
        raise IndexError
    upcoming = book.get_upcoming_birthdays()
    return "\n".join(upcoming) if upcoming else "🎂 No upcoming birthdays in the next 7 days."

@input_error
def add_address(args, book, command="addaddress"):
    if len(args) < 2:
        raise IndexError
    for i in range(1, len(args)):
        possible_name = normalize_name(" ".join(args[:i]))
        if book.name_exists(possible_name):
            name = possible_name
            address = " ".join(args[i:]).title()
            break
    else:
        return "😓 Contact not found."
    record = book.find(name)
    if record.address:
        return "😓 Address already exists. Use ‘editaddress’ to change it."
    record.add_address(address)
    return "✅ Address added!"

@input_error
def edit_address(args, book, command="editaddress"):
    if len(args) < 2:
        raise IndexError
    for i in range(1, len(args)):
        possible_name = normalize_name(" ".join(args[:i]))
        if book.name_exists(possible_name):
            name = possible_name
            new_address = " ".join(args[i:]).title()
            break
    else:
        return "😓 Contact not found."
    record = book.find(name)
    record.edit_address(new_address)
    return "✅ Address updated!"

@input_error
def remove_address(args, book, command="removeaddress"):
    if not args:
        raise IndexError
    name = normalize_name(" ".join(args))
    record = book.find(name)
    if not record:
        raise KeyError
    if not record.address:
        return "😓 Address is not set."
    record.remove_address()
    return "✅ Address removed!"

@input_error
def add_email(args, book, command="addemail"):
    if len(args) < 2:
        raise IndexError
    for i in range(1, len(args)):
        possible_name = normalize_name(" ".join(args[:i]))
        if book.name_exists(possible_name):
            name = possible_name
            email = " ".join(args[i:])
            break
    else:
        return "😓 Contact not found."
    record = book.find(name)
    if record.email:
        return "😓 Email already exists. Use ‘editemail’ to change it."
    record.add_email(email)
    return "✅ Email added!"

@input_error
def edit_email(args, book, command="editemail"):
    if len(args) < 2:
        raise IndexError
    for i in range(1, len(args)):
        possible_name = normalize_name(" ".join(args[:i]))
        if book.name_exists(possible_name):
            name = possible_name
            new_email = " ".join(args[i:])
            break
    else:
        return "😓 Contact not found."
    record = book.find(name)
    result = record.edit_email(new_email)
    if result is not None:
        return result

    return "✅ Email updated!"

@input_error
def remove_email(args, book, command="removeemail"):
    if not args:
        raise IndexError
    for i in range(1, len(args) + 1):
        possible_name = normalize_name(" ".join(args[:i]))
        if book.name_exists(possible_name):
            name = possible_name
            break
    else:
        return "😓 Please provide a valid contact name."

    record = book.find(name)
    if not record:
        return "😓 Contact not found."

    if not record.email:
        return "😓 Email is not set."

    record.remove_email()
    return "✅ Email removed!"

@input_error
def add_note(args, book, command="addnote"):
    if len(args) < 2:
        raise IndexError

    for i in range(1, len(args)):
        name_try = normalize_name(" ".join(args[:i]))
        if book.name_exists(name_try):
            name = name_try
            note_text = " ".join(args[i:])
            break
    else:
        return "😓 Contact not found."

    tags = extract_tags_from_text(note_text)
    clean_text = re.sub(r"#\w+", "", note_text).strip()

    record = book.find(name)
    note_result = record.add_note(clean_text, tags)

    if note_result is None:
        return f"😓 Note already exists. Use 'editnote' to modify it."
    return f"✅ Note added with tags: {', '.join(note_result.tags) if note_result.tags else 'none'}"

@input_error
def edit_note(args, book, command="editnote"):
    if len(args) < 3:
        raise IndexError

    for i in range(1, len(args)):
        name_try = normalize_name(" ".join(args[:i]))
        if book.name_exists(name_try):
            name = name_try
            break
    else:
        return "😓 Please provide the contact name, old note text and new note text."

    record = book.find(name)
    remaining = args[i:]

    for j in range(1, len(remaining)):
        old_candidate = " ".join(remaining[:j]).strip().lower()
        for note in record.notes:
            if note.text.strip().lower() == old_candidate:
                old_text = " ".join(remaining[:j])
                new_text = " ".join(remaining[j:])
                break
        else:
            continue
        break
    else:
        return "😓 Old note not found. Please check the old note text. Be exact."

    tags = extract_tags_from_text(new_text)
    clean_new_text = re.sub(r"#\w+", "", new_text).strip()

    result = record.edit_note(old_text, clean_new_text)
    if "edited" in result.lower():
        for note in record.notes:
            if note.text.strip().lower() == clean_new_text.lower():
                if tags:
                    note.tags = set(tags)
        return f"✅ Note updated{' with tags: ' + ', '.join(tags) if tags else ''}"
    return result
    
@input_error
def remove_note(args, book, command="removenote"):
    if not args:
        raise IndexError

    for i in range(1, len(args) + 1):
        possible_name = normalize_name(" ".join(args[:i]))
        if book.name_exists(possible_name):
            name = possible_name
            record = book.find(name)
            note_text = " ".join(args[i:]).strip()

            if not note_text:
                if not record.notes:
                    return f"ℹ️ No notes to remove for '{name}'."
                record.notes.clear()
                return f"🗑️ All notes removed for '{name}'."

            if record.remove_note(note_text):
                return "✅ Note removed!"
            else:
                return "😓 Note not found."
    return "🤔 Please provide the contact name and note text to remove."

@input_error
def search_note(args, book, command="searchnote"):
    if not args:
        raise IndexError

    query = " ".join(args).lower()
    matches = set()

    for record in book.values():
        name_match = query in record.name.value.lower()
        for note in record.notes:
            note_match = query in note.text.lower()
            if name_match or note_match:
                matches.add(f"{record.name.value}: {note}")

    return "\n".join(matches) if matches else "😓 No notes found."

@input_error
def add_tag_to_note(args, book, command="addtag"):
    if len(args) < 3:
        raise IndexError
    for i in range(1, len(args) - 1):
        name_try = normalize_name(" ".join(args[:i]))
        if book.name_exists(name_try):
            name = name_try
            break
    else:
        return "📝 Please provide the contact name, note text and tag to add."

    record = book.find(name)
    note_text = " ".join(args[i:-1])
    tag = args[-1].lstrip("#").lower()

    for note in record.notes:
        if note.text.strip().lower() == note_text.strip().lower():
            try:
                if tag in note.tags:
                    return f"⚠️ Tag '#{tag}' is already present in the note."
                note.add_tag(tag)
                return f"🏷️ Tag '#{tag}' added to note: {note.text}"
            except ValueError as ve:
                return str(ve)
    return "😓 Note not found. Please check the note text. Be exact."


@input_error
def remove_tag_from_note(args, book, command="removetag"):
    if len(args) < 2:
        raise IndexError

    for i in range(1, len(args) + 1):
        name_try = normalize_name(" ".join(args[:i]))
        if book.name_exists(name_try):
            name = name_try
            rest_args = args[i:]
            break
    else:
        return "😓 Please provide the contact name, note text and a tag to remove."

    if not rest_args:
        return "😓 Please provide the note text and a tag to remove."

    full_text = " ".join(rest_args)
    tag_match = re.search(r"#\w+", full_text)
    tag_to_remove = tag_match.group(0)[1:].lower() if tag_match else None
    note_text = re.sub(r"#\w+", "", full_text).strip()

    record = book.find(name)

    for note in record.notes:
        if note.text.strip().lower() == note_text.lower():
            if tag_to_remove:
                if tag_to_remove in note.tags:
                    note.tags.remove(tag_to_remove)
                    return f"🗑️ Tag '#{tag_to_remove}' removed from note: '{note.text}'"
                else:
                    return f"😓 Tag '#{tag_to_remove}' not found in this note."
            else:
                if note.tags:
                    note.tags.clear()
                    return f"🗑️ All tags removed from note: '{note.text}'"
                else:
                    return f"ℹ️ This note has no tags."
    return f"🤔 Please provide the note text and a tag to remove for '{name}'."

@input_error
def search_note_by_tag(args, book, command="searchtag"):
    if not args:
        raise IndexError
    tag = args[0].lstrip("#").lower()
    matches = []
    for record in book.values():
        for note in record.notes:
            if note.has_tag(tag):
                matches.append(f"{record.name.value}: {note}")
    return "\n".join(matches) if matches else f"😓 No notes with tag '#{tag}' found."


@input_error
def sort_note_by_tag(args, book, command="sorttag"):
    tag_map = {}

    for record in book.values():
        for note in record.notes:
            for tag in note.tags:
                tag = tag.lower()
                tag_map.setdefault(tag, []).append((record.name.value, note))

    if not tag_map:
        return "😓 No tagged notes to sort."

    result_lines = []
    for tag in sorted(tag_map):
        result_lines.append(f"📌 #{tag}")
        for name, note in tag_map[tag]:
            result_lines.append(f"{name}: {note}")
        result_lines.append("")  # empty line for spacing

    return "\n".join(result_lines)

def print_available_commands():
    command_groups = {
        "General": ["hello", "help", "exit", "close"],
        "Contacts": ["addcontact", "editname", "removecontact", "search", "all"],
        "Phones": ["addphone", "changephone", "removephone", "showphone", "search"],
        "Birthdays": ["addbday", "showbday", "editbday", "removebday", "search", "upcomingbdays"],
        "Email": ["addemail", "editemail", "removeemail", "search"],
        "Address": ["addaddress", "editaddress", "removeaddress", "search"],
        "Notes": ["addnote", "editnote", "removenote", "searchnote", "addtag", "removetag", "searchtag", "sorttag"]
    }
    table = Table(title="📋 Available Commands", show_header=True, header_style="bold green")
    table.add_column("Category", style="cyan", no_wrap=True)
    table.add_column("Commands", style="magenta")
    for category, commands in command_groups.items():
        command_list = ", ".join(commands)
        table.add_row(category, command_list)
    console.print(table)

def main():
    filename = DEFAULT_FILENAME
    book = load_address_book(filename)
    valid_commands = [
        "hello", "help", "exit", "close", "addcontact", "editname", "removecontact",
        "addphone", "changephone", "removephone", "showphone", "addbday", "showbday",
        "editbday", "removebday", "upcomingbdays", "search", "all", "addemail",
        "editemail", "removeemail", "addaddress", "editaddress", "removeaddress",
        "addnote", "editnote", "removenote", "searchnote", "addtag", 
        "removetag", "searchtag", "sorttag"
    ]
    console.print("😊 Welcome to the assistant bot!", style="green")
    console.print(f"Upcoming Birthdays:\n{upcoming_birthdays([], book)}", style="yellow")
    console.print("\nType 'help' to see available commands.", style="blue")
    try:
        while True:
            user_input = input("Enter a command: ")
            if not user_input.strip():
                console.print("😓 You didn’t enter anything! Please try again.", style="yellow")
                continue
            command, args = parse_input(user_input)
            if command in ["exit", "close", "ex"]:
                save_address_book(book, filename)
                console.print("👋 Good bye!", style="green")
                break
            elif command == "hello":
                console.print("😊 How can I help you?", style="green")
            elif command == "addcontact":
                result = add_contact(args, book, command="addcontact")
                console.print(result, style="green")
                if "added" in result.lower():
                    save_address_book(book, filename)
            elif command == "editname":
                result = edit_contact_name(args, book, command="editname")
                console.print(result, style="green")
                if "changed" in result.lower():
                    save_address_book(book, filename)
            elif command == "removecontact":
                result = remove_contact(args, book, command="removecontact")
                console.print(result, style="green")
                if "removed" in result.lower():
                    save_address_book(book, filename)
            elif command == "addphone":
                result = add_phone_to_contact(args, book, command="addphone")
                console.print(result, style="green")
                if "added" in result.lower():
                    save_address_book(book, filename)
            elif command == "changephone":
                result = change_contact(args, book, command="changephone")
                console.print(result, style="green")
                if "updated" in result.lower():
                    save_address_book(book, filename)
            elif command == "removephone":
                result = remove_phone(args, book, command="removephone")
                console.print(result, style="green")
                if "removed" in result.lower():
                    save_address_book(book, filename)
            elif command == "showphone":
                console.print(show_phone(args, book, command="showphone"), style="green")
            elif command == "addbday":
                result = add_birthday(args, book, command="addbday")
                console.print(result, style="green")
                if "added" in result.lower():
                    save_address_book(book, filename)
            elif command == "showbday":
                console.print(show_birthday(args, book, command="showbday"), style="green")
            elif command == "editbday":
                result = edit_birthday(args, book, command="editbday")
                console.print(result, style="green")
                if "updated" in result.lower():
                    save_address_book(book, filename)
            elif command == "removebday":
                result = remove_birthday(args, book, command="removebday")
                console.print(result, style="green")
                if "removed" in result.lower():
                    save_address_book(book, filename)
            elif command == "upcomingbdays":
                console.print(upcoming_birthdays(args, book, command="upcomingbdays"), style="green")
            elif command == "search":
                console.print(search_contacts(args, book, command="search"), style="green")
            elif command == "all":
                show_all_rich(book)
            elif command == "addemail":
                result = add_email(args, book, command="addemail")
                console.print(result, style="green")
                if "added" in result.lower():
                    save_address_book(book, filename)
            elif command == "editemail":
                result = edit_email(args, book, command="editemail")
                console.print(result, style="green")
                if "updated" in result.lower():
                    save_address_book(book, filename)
            elif command == "removeemail":
                result = remove_email(args, book, command="removeemail")
                console.print(result, style="green")
                if "removed" in result.lower():
                    save_address_book(book, filename)
            elif command == "addnote":
                result = add_note(args, book, command="addnote")
                console.print(result, style="green")
                if "added" in result.lower():
                    save_address_book(book, filename)
            elif command == "editnote":
                result = edit_note(args, book, command="editnote")
                console.print(result, style="green")
                if "updated" in result.lower():
                    save_address_book(book, filename)
            elif command == "removenote":
                result = remove_note(args, book, command="removenote")
                console.print(result, style="green")
                if "removed" in result.lower():
                    save_address_book(book, filename)
            elif command == "searchnote":
                console.print(search_note(args, book, command="searchnote"), style="green")
            elif command == "addtag":
                result = add_tag_to_note(args, book, command="addtag")
                console.print(result, style="green")
                save_address_book(book, filename)
            elif command == "removetag":
                result = remove_tag_from_note(args, book, command="removetag")
                console.print(result, style="green")
                save_address_book(book, filename)
            elif command == "searchtag":
                result = search_note_by_tag(args, book, command="searchtag")
                console.print(result, style="green")
            elif command == "sorttag":
                result = sort_note_by_tag(args, book, command="sorttag")
                console.print(result, style="green")
            elif command == "addaddress":
                result = add_address(args, book, command="addaddress")
                console.print(result, style="green")
                if "added" in result.lower():
                    save_address_book(book, filename)
            elif command == "editaddress":
                result = edit_address(args, book, command="editaddress")
                console.print(result, style="green")
                if "updated" in result.lower():
                    save_address_book(book, filename)
            elif command == "removeaddress":
                result = remove_address(args, book, command="removeaddress")
                console.print(result, style="green")
                if "removed" in result.lower():
                    save_address_book(book, filename)
            elif command == "help":
                print_available_commands()
            else:
                console.print(suggest_command(command, valid_commands), style="yellow")
    except KeyboardInterrupt:
        console.print("\n👋 Good bye!", style="green")
        save_address_book(book, filename)
        console.print("📚 Address book saved successfully.", style="green")

if __name__ == "__main__":
    main()