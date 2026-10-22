extends RefCounted
class_name Lang

# Localization helper built on top of Godot's TranslationServer.
# The source language (and translation keys) is English, pt_BR is provided
# through res://data/translations/pt_BR.tres (see [internationalization] in project.godot).
const Fallback : String						= "en"
const Supported : PackedStringArray			= ["en", "pt_BR"]
const Auto : String							= "auto"
const ConfKey : String						= "Interface-Language"

#
static func GetSaved() -> String:
	var saved = Conf.GetUserValue(ConfKey, Auto)
	return saved if saved is String else Auto

static func Resolve(language : String) -> String:
	if language in Supported:
		return language

	# "auto" or unknown value: pick the closest supported locale from the OS
	var osLocale : String = OS.get_locale()
	if osLocale in Supported:
		return osLocale

	var osLanguage : String = osLocale.get_slice("_", 0)
	for supported : String in Supported:
		if supported.get_slice("_", 0) == osLanguage:
			return supported

	return Fallback

static func Apply(language : String = GetSaved()):
	# Keep the headless server untranslated, every string sent through the
	# network protocol has to stay in the source language
	if "--server" in OS.get_cmdline_args():
		return
	TranslationServer.set_locale(Resolve(language))
