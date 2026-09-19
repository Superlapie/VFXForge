class_name VFXForgeThemeBuilder
extends RefCounted

const Tokens := preload("res://godot/ui/theme/tokens.gd")


static func apply(root: Control) -> void:
	root.theme = build()


static func build() -> Theme:
	var theme := Theme.new()
	theme.default_font_size = Tokens.FONT_UI

	_set_font_colors(theme)
	_set_buttons(theme)
	_set_inputs(theme)
	_set_panels(theme)
	_set_tree(theme)
	_set_tabs(theme)
	_set_separators(theme)
	_set_sliders(theme)
	_set_check_buttons(theme)
	_set_menus(theme)

	return theme


static func _set_font_colors(theme: Theme) -> void:
	theme.set_color("font_color", "Label", Tokens.TEXT_PRIMARY)
	theme.set_color("font_color", "Button", Tokens.TEXT_PRIMARY)
	theme.set_color("font_hover_color", "Button", Color.WHITE)
	theme.set_color("font_pressed_color", "Button", Color.WHITE)
	theme.set_color("font_disabled_color", "Button", Tokens.TEXT_MUTED)
	theme.set_color("font_color", "LineEdit", Tokens.TEXT_PRIMARY)
	theme.set_color("caret_color", "LineEdit", Tokens.ACCENT_CYAN)
	theme.set_color("font_color", "SpinBox", Tokens.TEXT_PRIMARY)
	theme.set_color("font_color", "OptionButton", Tokens.TEXT_PRIMARY)
	theme.set_color("font_color", "Tree", Tokens.TEXT_PRIMARY)
	theme.set_color("font_selected_color", "Tree", Color.WHITE)
	theme.set_color("font_hover_color", "Tree", Color.WHITE)
	theme.set_color("font_color", "TabBar", Tokens.TEXT_SECONDARY)
	theme.set_color("font_selected_color", "TabBar", Tokens.TEXT_PRIMARY)
	theme.set_color("font_hovered_color", "TabBar", Tokens.TEXT_PRIMARY)
	theme.set_color("font_color", "PopupMenu", Tokens.TEXT_PRIMARY)
	theme.set_color("font_hover_color", "PopupMenu", Color.WHITE)


static func _set_buttons(theme: Theme) -> void:
	theme.set_stylebox("normal", "Button", _flat_style(Tokens.PANEL_RAISED, Tokens.BORDER_SUBTLE, Tokens.RADIUS_SM))
	theme.set_stylebox("hover", "Button", _flat_style(Tokens.HOVER, Tokens.SEPARATOR, Tokens.RADIUS_SM))
	theme.set_stylebox("pressed", "Button", _flat_style(Tokens.SELECTION, Tokens.ACCENT_BLUE, Tokens.RADIUS_SM))
	theme.set_stylebox("disabled", "Button", _flat_style(Tokens.PANEL_BG, Tokens.PANEL_BG, Tokens.RADIUS_SM))
	theme.set_stylebox("focus", "Button", _flat_style(Tokens.HOVER, Tokens.ACCENT_CYAN, Tokens.RADIUS_SM))


static func _set_inputs(theme: Theme) -> void:
	theme.set_stylebox("normal", "LineEdit", _flat_style(Tokens.APP_BG, Tokens.BORDER_SUBTLE, Tokens.RADIUS_SM, 6, 4))
	theme.set_stylebox("focus", "LineEdit", _flat_style(Tokens.APP_BG, Tokens.ACCENT_CYAN, Tokens.RADIUS_SM, 6, 4))
	theme.set_stylebox("read_only", "LineEdit", _flat_style(Tokens.PANEL_BG, Tokens.SEPARATOR, Tokens.RADIUS_SM, 6, 4))
	theme.set_stylebox("normal", "OptionButton", _flat_style(Tokens.PANEL_RAISED, Tokens.BORDER_SUBTLE, Tokens.RADIUS_SM))
	theme.set_stylebox("hover", "OptionButton", _flat_style(Tokens.HOVER, Tokens.SEPARATOR, Tokens.RADIUS_SM))
	theme.set_stylebox("pressed", "OptionButton", _flat_style(Tokens.SELECTION, Tokens.ACCENT_BLUE, Tokens.RADIUS_SM))
	theme.set_stylebox("focus", "OptionButton", _flat_style(Tokens.HOVER, Tokens.ACCENT_CYAN, Tokens.RADIUS_SM))


static func _set_panels(theme: Theme) -> void:
	var panel := _flat_style(Tokens.PANEL_BG, Color.TRANSPARENT, 0, Tokens.SPACE_SM, Tokens.SPACE_SM)
	theme.set_stylebox("panel", "PanelContainer", panel)
	theme.set_stylebox("panel", "Panel", panel)


static func _set_tree(theme: Theme) -> void:
	theme.set_color("selection_color", "Tree", Tokens.SELECTION)
	theme.set_stylebox("panel", "Tree", _flat_style(Tokens.PANEL_BG, Color.TRANSPARENT, 0))


static func _set_tabs(theme: Theme) -> void:
	theme.set_stylebox("tab_unselected", "TabBar", _flat_style(Color.TRANSPARENT, Color.TRANSPARENT, 0, Tokens.SPACE_SM, 4))
	theme.set_stylebox("tab_hovered", "TabBar", _flat_style(Tokens.HOVER, Color.TRANSPARENT, Tokens.RADIUS_SM, Tokens.SPACE_SM, 4))
	theme.set_stylebox("tab_selected", "TabBar", _flat_style(Tokens.PANEL_RAISED, Color.TRANSPARENT, Tokens.RADIUS_SM, Tokens.SPACE_SM, 4))
	theme.set_stylebox("tab_focus", "TabBar", _flat_style(Tokens.HOVER, Tokens.ACCENT_CYAN, Tokens.RADIUS_SM, Tokens.SPACE_SM, 4))


static func _set_separators(theme: Theme) -> void:
	var sep := StyleBoxLine.new()
	sep.color = Tokens.SEPARATOR
	sep.vertical = true
	theme.set_stylebox("separator", "HSeparator", sep)
	var sep_h := StyleBoxLine.new()
	sep_h.color = Tokens.SEPARATOR
	theme.set_stylebox("separator", "VSeparator", sep_h)


static func _set_sliders(theme: Theme) -> void:
	theme.set_stylebox("slider", "HSlider", _flat_style(Tokens.APP_BG, Color.TRANSPARENT, Tokens.RADIUS_SM, 2, 2))
	theme.set_stylebox("grabber_area", "HSlider", _flat_style(Tokens.PANEL_RAISED, Color.TRANSPARENT, Tokens.RADIUS_SM))
	theme.set_stylebox("grabber_area_highlight", "HSlider", _flat_style(Tokens.HOVER, Color.TRANSPARENT, Tokens.RADIUS_SM))


static func _set_check_buttons(theme: Theme) -> void:
	theme.set_color("font_color", "CheckButton", Tokens.TEXT_PRIMARY)
	theme.set_color("font_hover_color", "CheckButton", Color.WHITE)


static func _set_menus(theme: Theme) -> void:
	theme.set_stylebox("panel", "PopupMenu", _flat_style(Tokens.PANEL_RAISED, Tokens.BORDER_SUBTLE, Tokens.RADIUS_MD))
	theme.set_stylebox("hover", "PopupMenu", _flat_style(Tokens.HOVER, Color.TRANSPARENT, Tokens.RADIUS_SM))


static func _flat_style(
	fill: Color,
	border: Color,
	radius: int,
	margin_h: int = Tokens.SPACE_SM,
	margin_v: int = 5,
) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	if border.a > 0.0:
		style.border_color = border
		style.border_width_left = 1
		style.border_width_right = 1
		style.border_width_top = 1
		style.border_width_bottom = 1
	style.corner_radius_top_left = radius
	style.corner_radius_top_right = radius
	style.corner_radius_bottom_left = radius
	style.corner_radius_bottom_right = radius
	style.content_margin_left = margin_h
	style.content_margin_right = margin_h
	style.content_margin_top = margin_v
	style.content_margin_bottom = margin_v
	return style
