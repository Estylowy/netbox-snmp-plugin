from django import template

register = template.Library()


@register.inclusion_tag(
    "netbox_snmp_plugin/snmp_panel.html",
    takes_context=True,
)
def snmp_panel(context):
    device = context.get("object")
    return {"device": device}
