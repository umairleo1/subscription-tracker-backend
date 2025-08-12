import re
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from decimal import Decimal
from dataclasses import dataclass

@dataclass
class ParsedSubscription:
    service_name: str
    cost: Optional[Decimal] = None
    currency: str = "USD"
    billing_cycle: Optional[str] = None
    next_billing_date: Optional[datetime] = None
    confidence_score: float = 0.0
    parsing_method: str = "regex"

class EmailPatternMatcher:
    
    def __init__(self):
        self.patterns = self._load_patterns()
    
    def _load_patterns(self) -> Dict:
        return {
            "netflix": {
                "senders": [r"info@netflix\.com", r"netflix@.*"],
                "subjects": [r"your netflix bill", r"netflix payment", r"netflix subscription"],
                "service_indicators": [r"netflix", r"streaming"],
                "cost_patterns": [r"\$(\d+\.?\d*)", r"(\d+\.?\d*) usd"],
                "billing_cycle": [r"monthly", r"month", r"per month"]
            },
            "spotify": {
                "senders": [r"spotify@.*", r"no-reply@spotify\.com"],
                "subjects": [r"spotify premium", r"your spotify", r"payment confirmation"],
                "service_indicators": [r"spotify", r"premium", r"music"],
                "cost_patterns": [r"\$(\d+\.?\d*)", r"(\d+\.?\d*) usd"],
                "billing_cycle": [r"monthly", r"month", r"per month"]
            },
            "adobe": {
                "senders": [r"adobe@.*", r"noreply@adobe\.com"],
                "subjects": [r"adobe", r"creative cloud", r"subscription"],
                "service_indicators": [r"adobe", r"creative cloud", r"photoshop"],
                "cost_patterns": [r"\$(\d+\.?\d*)", r"(\d+\.?\d*) usd"],
                "billing_cycle": [r"monthly", r"month", r"annually", r"year"]
            }
        }
    
    def match_service(self, sender: str, subject: str, body: str) -> Optional[str]:
        sender_lower = sender.lower()
        subject_lower = subject.lower()
        body_lower = body.lower()
        
        for service, patterns in self.patterns.items():
            # Check sender patterns
            for pattern in patterns["senders"]:
                if re.search(pattern, sender_lower):
                    return service
            
            # Check subject patterns
            for pattern in patterns["subjects"]:
                if re.search(pattern, subject_lower):
                    return service
            
            # Check body for service indicators
            for pattern in patterns["service_indicators"]:
                if re.search(pattern, body_lower):
                    return service
        
        return None
    
    def extract_cost(self, text: str, service: str) -> Optional[Tuple[Decimal, str]]:
        if service not in self.patterns:
            return None
        
        patterns = self.patterns[service]["cost_patterns"]
        for pattern in patterns:
            matches = re.findall(pattern, text.lower())
            if matches:
                try:
                    cost = Decimal(matches[0])
                    return cost, "USD"  # Default currency
                except:
                    continue
        
        return None
    
    def extract_billing_cycle(self, text: str, service: str) -> Optional[str]:
        if service not in self.patterns:
            return None
        
        patterns = self.patterns[service]["billing_cycle"]
        text_lower = text.lower()
        
        for pattern in patterns:
            if re.search(pattern, text_lower):
                if "month" in pattern:
                    return "monthly"
                elif "year" in pattern or "annual" in pattern:
                    return "annually"
                elif "quarter" in pattern:
                    return "quarterly"
        
        return None

class EmailProcessor:
    
    def __init__(self):
        self.pattern_matcher = EmailPatternMatcher()
        self.general_patterns = self._load_general_patterns()
    
    def _load_general_patterns(self) -> Dict:
        return {
            "subscription_keywords": [
                r"subscription", r"recurring", r"renewal", r"billing",
                r"payment", r"invoice", r"receipt", r"charge"
            ],
            "money_patterns": [
                r"\$(\d+\.?\d*)",
                r"(\d+\.?\d*)\s*usd",
                r"(\d+\.?\d*)\s*dollars?",
                r"total:?\s*\$?(\d+\.?\d*)"
            ],
            "date_patterns": [
                r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})",
                r"(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})",
                r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+\d{1,2},?\s+\d{4}"
            ]
        }
    
    def is_subscription_related(self, sender: str, subject: str, body: str) -> bool:
        text = f"{sender} {subject} {body}".lower()
        
        for keyword in self.general_patterns["subscription_keywords"]:
            if re.search(keyword, text):
                return True
        
        return False
    
    def parse_email(self, sender: str, subject: str, body: str, email_date: datetime) -> Optional[ParsedSubscription]:
        if not self.is_subscription_related(sender, subject, body):
            return None
        
        # Try to match a known service
        service = self.pattern_matcher.match_service(sender, subject, body)
        
        if service:
            return self._parse_known_service(service, sender, subject, body, email_date)
        else:
            return self._parse_generic_subscription(sender, subject, body, email_date)
    
    def _parse_known_service(self, service: str, sender: str, subject: str, body: str, email_date: datetime) -> ParsedSubscription:
        full_text = f"{subject} {body}"
        
        # Extract cost
        cost_info = self.pattern_matcher.extract_cost(full_text, service)
        cost = cost_info[0] if cost_info else None
        currency = cost_info[1] if cost_info else "USD"
        
        # Extract billing cycle
        billing_cycle = self.pattern_matcher.extract_billing_cycle(full_text, service)
        
        return ParsedSubscription(
            service_name=service.title(),
            cost=cost,
            currency=currency,
            billing_cycle=billing_cycle,
            confidence_score=0.9 if cost and billing_cycle else 0.7,
            parsing_method="regex_pattern"
        )
    
    def _parse_generic_subscription(self, sender: str, subject: str, body: str, email_date: datetime) -> ParsedSubscription:
        full_text = f"{subject} {body}"
        
        # Extract service name from sender or subject
        service_name = self._extract_service_name(sender, subject)
        
        # Extract cost
        cost = self._extract_generic_cost(full_text)
        
        # Extract billing cycle
        billing_cycle = self._extract_generic_billing_cycle(full_text)
        
        return ParsedSubscription(
            service_name=service_name,
            cost=cost,
            currency="USD",
            billing_cycle=billing_cycle,
            confidence_score=0.6,
            parsing_method="regex_generic"
        )
    
    def _extract_service_name(self, sender: str, subject: str) -> str:
        # Try to extract service name from sender email
        sender_parts = sender.split('@')
        if len(sender_parts) > 1:
            domain = sender_parts[1].split('.')[0]
            # Clean up common prefixes
            if domain not in ['noreply', 'no-reply', 'info', 'billing', 'support']:
                return domain.title()
        
        # Fallback to subject
        words = subject.split()
        for word in words:
            if len(word) > 2 and word.isalpha():
                return word.title()
        
        return "Unknown Service"
    
    def _extract_generic_cost(self, text: str) -> Optional[Decimal]:
        for pattern in self.general_patterns["money_patterns"]:
            matches = re.findall(pattern, text.lower())
            if matches:
                try:
                    return Decimal(matches[0])
                except:
                    continue
        return None
    
    def _extract_generic_billing_cycle(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        
        if re.search(r"monthly|month|per month", text_lower):
            return "monthly"
        elif re.search(r"annually|annual|year|yearly|per year", text_lower):
            return "annually"
        elif re.search(r"quarterly|quarter", text_lower):
            return "quarterly"
        elif re.search(r"weekly|week|per week", text_lower):
            return "weekly"
        
        return None

class AdvancedEmailProcessor:
    
    def __init__(self):
        self.basic_processor = EmailProcessor()
    
    def process_with_confidence_scoring(self, emails: List[Dict]) -> List[Dict]:
        results = []
        
        for email in emails:
            parsed = self.basic_processor.parse_email(
                email['sender'],
                email['subject'],
                email['body'],
                email['date']
            )
            
            if parsed:
                result = {
                    'email_id': email['id'],
                    'parsed_subscription': parsed,
                    'requires_gpt_processing': parsed.confidence_score < 0.7,
                    'requires_user_review': parsed.confidence_score < 0.5
                }
                results.append(result)
        
        return results
    
    def prepare_for_gpt_processing(self, low_confidence_results: List[Dict]) -> List[Dict]:
        gpt_prompts = []
        
        for result in low_confidence_results:
            if result['requires_gpt_processing']:
                prompt = self._create_gpt_prompt(result)
                gpt_prompts.append({
                    'email_id': result['email_id'],
                    'prompt': prompt,
                    'fallback_data': result['parsed_subscription']
                })
        
        return gpt_prompts
    
    def _create_gpt_prompt(self, result: Dict) -> str:
        return f"""
        Analyze this email for subscription information:
        
        Email details:
        - Sender: {result['email_sender']}
        - Subject: {result['email_subject']}
        - Body: {result['email_body']}
        
        Extract:
        1. Service name
        2. Cost (amount and currency)
        3. Billing cycle (monthly, annually, etc.)
        4. Next billing date if mentioned
        5. Is this a subscription confirmation, renewal notice, or receipt?
        
        Respond with JSON format only.
        """