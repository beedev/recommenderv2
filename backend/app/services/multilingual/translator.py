"""
Multilingual Translation Service
LLM-based translation with fallback support for S1→S7 Configurator
"""

import logging
import os
from typing import Optional
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class MultilingualTranslator:
    """
    LLM-powered translation service for welding equipment configurator

    Supported Languages (ISO 639-1):
    - en: English (default)
    - es: Spanish
    - fr: French
    - de: German
    - pt: Portuguese
    - it: Italian
    - sv: Swedish
    """

    # Language names for system prompts
    LANGUAGE_NAMES = {
        "en": "English",
        "es": "Spanish",
        "fr": "French",
        "de": "German",
        "pt": "Portuguese",
        "it": "Italian",
        "sv": "Swedish"
    }

    # Fallback translations for common phrases (when LLM unavailable)
    FALLBACK_TRANSLATIONS = {
        "es": {
            "Select a power source": "Seleccione una fuente de alimentación",
            "Select a feeder": "Seleccione un alimentador",
            "Select a cooler": "Seleccione un enfriador",
            "Select an interconnector": "Seleccione un interconector",
            "Select a torch": "Seleccione una antorcha",
            "Select accessories": "Seleccione accesorios",
            "Configuration complete": "Configuración completa",
            "Here are compatible products": "Aquí hay productos compatibles",
            "No products found": "No se encontraron productos",
            "Product selected successfully": "Producto seleccionado exitosamente"
        },
        "fr": {
            "Select a power source": "Sélectionnez une source d'alimentation",
            "Select a feeder": "Sélectionnez un dévidoir",
            "Select a cooler": "Sélectionnez un refroidisseur",
            "Select an interconnector": "Sélectionnez un interconnecteur",
            "Select a torch": "Sélectionnez une torche",
            "Select accessories": "Sélectionnez des accessoires",
            "Configuration complete": "Configuration terminée",
            "Here are compatible products": "Voici les produits compatibles",
            "No products found": "Aucun produit trouvé",
            "Product selected successfully": "Produit sélectionné avec succès"
        },
        "de": {
            "Select a power source": "Wählen Sie eine Stromquelle",
            "Select a feeder": "Wählen Sie einen Drahtvorschub",
            "Select a cooler": "Wählen Sie einen Kühler",
            "Select an interconnector": "Wählen Sie einen Verbinder",
            "Select a torch": "Wählen Sie einen Brenner",
            "Select accessories": "Wählen Sie Zubehör",
            "Configuration complete": "Konfiguration abgeschlossen",
            "Here are compatible products": "Hier sind kompatible Produkte",
            "No products found": "Keine Produkte gefunden",
            "Product selected successfully": "Produkt erfolgreich ausgewählt"
        },
        "pt": {
            "Select a power source": "Selecione uma fonte de energia",
            "Select a feeder": "Selecione um alimentador",
            "Select a cooler": "Selecione um resfriador",
            "Select an interconnector": "Selecione um interconector",
            "Select a torch": "Selecione uma tocha",
            "Select accessories": "Selecione acessórios",
            "Configuration complete": "Configuração completa",
            "Here are compatible products": "Aqui estão produtos compatíveis",
            "No products found": "Nenhum produto encontrado",
            "Product selected successfully": "Produto selecionado com sucesso"
        },
        "it": {
            "Select a power source": "Seleziona una fonte di alimentazione",
            "Select a feeder": "Seleziona un alimentatore",
            "Select a cooler": "Seleziona un refrigeratore",
            "Select an interconnector": "Seleziona un interconnettore",
            "Select a torch": "Seleziona una torcia",
            "Select accessories": "Seleziona accessori",
            "Configuration complete": "Configurazione completata",
            "Here are compatible products": "Ecco i prodotti compatibili",
            "No products found": "Nessun prodotto trovato",
            "Product selected successfully": "Prodotto selezionato con successo"
        },
        "sv": {
            "Select a power source": "Välj en strömkälla",
            "Select a feeder": "Välj en matare",
            "Select a cooler": "Välj en kylare",
            "Select an interconnector": "Välj en sammankoppling",
            "Select a torch": "Välj en svetsbrännare",
            "Select accessories": "Välj tillbehör",
            "Configuration complete": "Konfiguration klar",
            "Here are compatible products": "Här är kompatibla produkter",
            "No products found": "Inga produkter hittades",
            "Product selected successfully": "Produkt har valts framgångsrikt"
        }
    }

    def __init__(self):
        """Initialize OpenAI client for translations"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY not set - translations will use fallback only")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=api_key)

        logger.info("Multilingual Translator initialized")

    async def translate(
        self,
        text: str,
        target_language: str,
        context: Optional[str] = None
    ) -> str:
        """
        Translate text to target language using LLM

        Args:
            text: English text to translate
            target_language: ISO 639-1 language code (es, fr, de, pt, it, sv)
            context: Optional context about the text (e.g., "welding equipment configurator prompt")

        Returns:
            Translated text in target language
        """

        # No translation needed for English
        if target_language == "en":
            return text

        # Validate language code
        if target_language not in self.LANGUAGE_NAMES:
            logger.warning(f"Unsupported language: {target_language}, defaulting to English")
            return text

        # Try LLM translation first
        if self.client:
            try:
                translated = await self._llm_translate(text, target_language, context)
                return translated
            except Exception as e:
                logger.error(f"LLM translation failed: {e}, using fallback")

        # Fallback to simple translation
        return self._fallback_translate(text, target_language)

    async def _llm_translate(
        self,
        text: str,
        target_language: str,
        context: Optional[str]
    ) -> str:
        """Use OpenAI LLM for natural translation"""

        language_name = self.LANGUAGE_NAMES[target_language]

        # Build translation prompt
        system_prompt = f"""You are a professional translator specializing in welding equipment and industrial terminology.

Translate the following text from English to {language_name}.

IMPORTANT RULES:
1. Maintain technical accuracy for welding terms (Power Source, Feeder, Cooler, etc.)
2. Keep product names and GIN codes unchanged
3. Use natural, conversational phrasing appropriate for {language_name}
4. Preserve any formatting (line breaks, bullet points, etc.)
5. Do not add explanations or notes, only provide the translation

Context: {context or 'Welding equipment configurator interface'}
"""

        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                temperature=0.3,  # Low temperature for consistent translations
                max_tokens=500
            )

            translated = response.choices[0].message.content.strip()
            logger.debug(f"LLM translated '{text[:50]}...' to {target_language}")
            return translated

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def _fallback_translate(self, text: str, target_language: str) -> str:
        """Simple fallback translation using predefined phrases"""

        if target_language not in self.FALLBACK_TRANSLATIONS:
            return text

        translations = self.FALLBACK_TRANSLATIONS[target_language]

        # Check if text matches any predefined phrase
        if text in translations:
            return translations[text]

        # Check for partial matches
        for english_phrase, translated_phrase in translations.items():
            if english_phrase in text:
                text = text.replace(english_phrase, translated_phrase)

        return text

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes"""
        return list(self.LANGUAGE_NAMES.keys())

    def get_language_name(self, code: str) -> str:
        """Get full language name from code"""
        return self.LANGUAGE_NAMES.get(code, "Unknown")


# Singleton instance
_translator: Optional[MultilingualTranslator] = None


def get_translator() -> MultilingualTranslator:
    """Get singleton translator instance"""
    global _translator
    if _translator is None:
        _translator = MultilingualTranslator()
    return _translator
