class_name VFXExportRunner
extends RefCounted

## Runs vfxforge export against a saved canonical document.


static func resolve_document_path(source_path: String) -> String:
	if source_path.is_empty():
		return ""
	if source_path.begins_with("res://"):
		return ProjectSettings.globalize_path(source_path)
	return source_path


static func default_output_dir(source_path: String, document: Dictionary) -> String:
	var global_source := resolve_document_path(source_path)
	if global_source.is_empty():
		return ""
	var export_settings: Dictionary = document.get("export", {})
	var folder_name := str(export_settings.get("folder_name", document.get("id", "effect")))
	return global_source.get_base_dir().path_join("exports").path_join(folder_name)


static func run_export(source_path: String, output_dir: String) -> Dictionary:
	var document_path := resolve_document_path(source_path)
	if document_path.is_empty() or not FileAccess.file_exists(document_path):
		return {
			"success": false,
			"message": "Save the effect to a .vfx.json file before exporting.",
			"output": "",
			"result": {},
		}
	var output := PackedStringArray()
	var exit_code := OS.execute(
		"python3",
		["-m", "vfxforge", "export", document_path, "--output", output_dir],
		output,
		true,
		false
	)
	var combined := "\n".join(output)
	var parsed: Dictionary = _parse_cli_json(combined)
	var success := exit_code == 0 and bool(parsed.get("success", false))
	var message := "Exported to " + output_dir
	if not success:
		var errors: Array = parsed.get("errors", [])
		if not errors.is_empty() and errors[0] is Dictionary:
			message = str(errors[0].get("message", "Export failed."))
		elif not combined.is_empty():
			var lines := combined.strip_edges().split("\n")
			message = lines[lines.size() - 1]
		else:
			message = "Export failed with exit code " + str(exit_code)
	return {
		"success": success,
		"message": message,
		"output": combined,
		"result": parsed,
		"output_dir": output_dir,
	}


static func _parse_cli_json(combined: String) -> Dictionary:
	for line in combined.split("\n"):
		var trimmed := line.strip_edges()
		if trimmed.is_empty() or not trimmed.begins_with("{"):
			continue
		var parsed: Variant = JSON.parse_string(trimmed)
		if parsed is Dictionary:
			return parsed
	var parsed_all: Variant = JSON.parse_string(combined.strip_edges())
	return parsed_all if parsed_all is Dictionary else {}
