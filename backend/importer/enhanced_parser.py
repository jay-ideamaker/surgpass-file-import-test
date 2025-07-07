import re
from bs4 import BeautifulSoup
from .models import Question, AnswerChoice, Article, QuickHit, QuickHitAnswerChoice

# --- Main Parsing Logic ---

def parse_new_format_enhanced(full_html):
    """
    Parses the new format by slicing the HTML document into logical sections
    and then processing each section individually to preserve context and formatting.
    """
    print("[PARSER_INFO] Processing NEW FORMAT document (FINAL version)...")
    
    soup = BeautifulSoup(full_html, 'html.parser')
    
    # 1. Slice the document into logical HTML chunks using the robust method
    sections = _slice_document_by_headings_robust(soup)

    # 2. Extract metadata from the header section
    metadata = _extract_metadata(sections.get('header', ''))
    
    # 3. Extract content from their dedicated sections
    metadata['question_text'] = _extract_question_text_from_header(sections.get('header', ''))
    metadata['short_explanation'] = sections.get('key_point', '')
    metadata['full_explanation'] = sections.get('expanded_explanation', '')
    
    print(f"  [METADATA] {metadata}")

    # 4. Create the question object with all data at once
    question = Question.objects.create(**metadata)
    print(f"  [DB_SAVE] Created Question: {question.id}")

    # 5. Process related objects using their dedicated HTML sections
    _create_answer_choices_combined(question, sections.get('header'), sections.get('commentary'))
    _create_references(question, sections.get('references'))
    _create_quickhits(question, sections.get('quickhits'))
    
    print("--- Finished Processing Question ---")
    return [question.id]


# --- Slicing and Helper Functions (ROBUST VERSION) ---

def _slice_document_by_headings_robust(soup):
    """
    A robust slicer that finds all <p> tags and divides them into sections
    based on the linear position of known headings.
    """
    sections = {}
    headings_in_order = [
        "Key Point", "Expanded Explanation", "Answer-by-Answer Commentary",
        "References", "Image Source", "QUICKHITS"
    ]
    
    all_p_tags = soup.find_all('p')
    found_headings = []

    # First, find the locations of all our headings
    for i, p_tag in enumerate(all_p_tags):
        # Use a specific regex to find headings at the start of a paragraph
        text = p_tag.get_text(strip=True)
        # The regex looks for a heading followed by a dash or end-of-string
        match = re.match(r'^\s*(' + r'|'.join(headings_in_order) + r')\s*(?:–|-|$)', text)
        if match:
            heading_key = match.group(1).strip()
            found_headings.append({'key': heading_key, 'index': i})

    # The header is everything before the first heading
    first_heading_index = found_headings[0]['index'] if found_headings else len(all_p_tags)
    sections['header'] = "".join(str(p) for p in all_p_tags[:first_heading_index])

    # Process each section between the headings
    for i, heading_info in enumerate(found_headings):
        start_index = heading_info['index'] + 1  # Content starts *after* the heading tag
        end_index = found_headings[i + 1]['index'] if i + 1 < len(found_headings) else len(all_p_tags)
        
        section_key = heading_info['key'].lower().replace(' ', '_').replace('-', '_')
        if 'answer_by_answer' in section_key:
            section_key = 'commentary'
        
        sections[section_key] = "".join(str(p) for p in all_p_tags[start_index:end_index])
        
    return sections

def _extract_metadata(header_html):
    """Extracts metadata from the initial text block of the document."""
    if not header_html: return {}
    soup = BeautifulSoup(header_html, 'html.parser')
    text = soup.get_text(separator='\n')
    data = {}
    
    absite_match = re.search(r'^Blueprint tag \(ABSITE\):\s*(.*)$', text, re.M)
    absqe_match = re.search(r'^Blueprint tag \(ABS QE\):\s*(.*)$', text, re.M)
    
    if absite_match:
        data['question_bank'] = 'ABSITE'
        data['blueprint'] = absite_match.group(1).strip()
    elif absqe_match:
        data['question_bank'] = 'ABS QE'
        data['blueprint'] = absqe_match.group(1).strip()
        
    subject_match = re.search(r'^Subject tag:\s*(.*)$', text, re.M)
    if subject_match: data['subject'] = subject_match.group(1).strip()
        
    topic_match = re.search(r'^Topic tag:\s*(.*)$', text, re.M)
    if topic_match: data['topic'] = topic_match.group(1).strip()
        
    return data

def _extract_question_text_from_header(header_html):
    """Finds the actual question text, stopping before the answer choices."""
    if not header_html: return ""
    soup = BeautifulSoup(header_html, 'html.parser')
    last_meta_tag = soup.find(string=re.compile(r'Topic tag:'))
    if not last_meta_tag: return ""

    question_html = []
    start_node = last_meta_tag.find_parent('p')
    if not start_node: return ""

    for sibling in start_node.find_next_siblings():
        if sibling.name == 'p' and re.match(r'^[A-E]\.', sibling.get_text(strip=True)):
            break
        question_html.append(str(sibling))
        
    return "".join(question_html).strip()


# --- Content-Specific Parsers ---

def _create_answer_choices_combined(question, header_html, commentary_html):
    """
    Parses choices from the header and explanations from the commentary,
    then combines them into complete AnswerChoice objects.
    """
    if not header_html:
        print("  [ANSWERS] No header section found to parse choices.")
        return

    header_soup = BeautifulSoup(header_html, 'html.parser')
    
    choice_texts = {}
    choice_tags_in_header = header_soup.find_all('p', string=re.compile(r'^[A-E]\.'))
    for tag in choice_tags_in_header:
        text = tag.get_text(strip=True)
        letter = text[0]
        choice_text = text.lstrip(f'{letter}.').strip()
        choice_texts[letter] = choice_text

    choice_explanations = {}
    if commentary_html:
        commentary_soup = BeautifulSoup(commentary_html, 'html.parser')
        explanation_tags = commentary_soup.find_all('p', string=re.compile(r'^[A-E]\.'))
        for tag in explanation_tags:
            text = tag.get_text(strip=True)
            letter = text[0]
            explanation_html = tag.decode_contents().lstrip(f'{letter}.').strip()
            choice_explanations[letter] = explanation_html

    correct_letter_match = re.search(r'Correct answer:\s*([A-E])', header_soup.get_text())
    correct_letter = correct_letter_match.group(1) if correct_letter_match else None

    count = 0
    for letter, text in choice_texts.items():
        AnswerChoice.objects.create(
            question=question,
            text=text, # Correctly use the parsed text
            is_correct=(letter == correct_letter),
            explanation=choice_explanations.get(letter, '')
        )
        count += 1
    print(f"  [ANSWERS] Created {count} choices with explanations, correct: {correct_letter}")


def _create_references(question, references_html):
    """Parses the 'References' section."""
    if not references_html:
        print("  [REFERENCES] No references section found.")
        return
    
    soup = BeautifulSoup(references_html, 'html.parser')
    ref_tags = [p for p in soup.find_all('p') if p.get_text(strip=True)]
    for tag in ref_tags:
        Article.objects.create(question=question, text=tag.decode_contents().strip())
    print(f"  [REFERENCES] Created {len(ref_tags)} references.")


def _create_quickhits(question, quickhits_html):
    """Parses the 'QUICKHITS' section."""
    if not quickhits_html:
        print("  [QUICKHITS] No QuickHits section found.")
        return

    soup = BeautifulSoup(quickhits_html, 'html.parser')
    # Split the QuickHits section by the bolded QuickHit headings
    # The use of '(?=...)' is a positive lookahead to split *before* the tag
    qh_blocks_html = re.split(r'(?=<p><strong>QuickHit #?\d+)', quickhits_html)
    
    count = 0
    for block_html in qh_blocks_html:
        if not block_html or not block_html.strip():
            continue

        block_soup = BeautifulSoup(block_html, 'html.parser')
        block_text = block_soup.get_text(separator='\n')

        stem_match = re.search(r'Stem:\s*(.+?)(?=\n[A-Z]\.|$)', block_text, re.S)
        if not stem_match: continue
        
        stem_text = stem_match.group(1).strip()
        rationale_match = re.search(r'One-line rationale:\s*(.+)', block_text)
        rationale_text = rationale_match.group(1).strip() if rationale_match else ''
        correct_match = re.search(r'Correct answer:\s*([A-E])', block_text)
        correct_letter = correct_match.group(1) if correct_match else None
        
        qh = QuickHit.objects.create(
            parent_question=question,
            question_text=stem_text,
            rationale=rationale_text
        )
        
        choices = re.findall(r'^([A-E])\.\s*(.+?)$', block_text, re.M)
        for letter, text in choices:
            QuickHitAnswerChoice.objects.create(
                quick_hit=qh,
                text=f"{letter}. {text.strip()}",
                is_correct=(letter == correct_letter)
            )
        count += 1
    print(f"  [QUICKHITS] Created {count} QuickHits.")