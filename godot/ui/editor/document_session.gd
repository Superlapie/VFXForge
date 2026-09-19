class_name VFXDocumentSession
extends RefCounted

const EditorStateScript := preload("res://godot/ui/editor/editor_state.gd")

var session_id: String = ""
var model: VFXDocument
var source_path: String = ""
var selected_layer_id: String = ""
var editor_state: VFXEditorState = EditorStateScript.new()
var undo_redo := UndoRedo.new()
var should_auto_frame := false
var display_name := "Untitled Effect"


static func create(model: VFXDocument, source_path: String, session_id: String = "") -> VFXDocumentSession:
	var session := VFXDocumentSession.new()
	session.session_id = session_id if not session_id.is_empty() else str(Time.get_ticks_usec())
	session.model = model
	session.source_path = source_path
	session.display_name = str(model.data.get("name", "Untitled Effect"))
	return session


func tab_label(is_dirty: bool) -> String:
	return display_name + (" ●" if is_dirty else "")


func path_key() -> String:
	return source_path if not source_path.is_empty() else session_id
