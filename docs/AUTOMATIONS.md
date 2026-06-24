# Automation examples

Practical examples using the entities and events this integration provides.
Replace the entity IDs and device names with your own (find them under
**Settings → Devices & Services → FlashForge → your printer**).

See also: [Status / Print Status value reference](STATUS.md).

---

## Notify when a print finishes

The integration fires a `flashforge_print_finished` event on the bus when a
job completes. The event data contains `device_id`, `name`, `file` and
`status`.

```yaml
automation:
  - alias: "Notify when 3D print finishes"
    trigger:
      - platform: event
        event_type: flashforge_print_finished
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Print finished 🎉"
          message: "{{ trigger.event.data.name }} finished printing {{ trigger.event.data.file }}"
```

## Notify on a printer error

```yaml
automation:
  - alias: "Notify on 3D printer error"
    trigger:
      - platform: event
        event_type: flashforge_error
    action:
      - service: notify.mobile_app_my_phone
        data:
          title: "Printer error ⚠️"
          message: "{{ trigger.event.data.name }} reported an error (status {{ trigger.event.data.status }})."
```

> The same outcomes can be triggered from the **binary sensors** instead of the
> events — e.g. trigger on `binary_sensor.<printer>_printing` turning `off`, or
> `binary_sensor.<printer>_error` turning `on`. The events are simply a
> discrete, one-shot signal that's convenient for notifications.

## Announce the estimated finish time

On new-API printers the `finish_time` sensor is a timestamp, so you can read it
directly:

```yaml
automation:
  - alias: "Announce print ETA when a print starts"
    trigger:
      - platform: state
        entity_id: binary_sensor.creator_5_printing
        to: "on"
    action:
      - service: notify.mobile_app_my_phone
        data:
          message: >
            Print started. Estimated finish:
            {{ as_timestamp(states('sensor.creator_5_finish_time')) | timestamp_custom('%H:%M') }}.
```

## Turn a smart plug off after the print cools down

```yaml
automation:
  - alias: "Power off printer plug after cooldown"
    trigger:
      - platform: event
        event_type: flashforge_print_finished
    action:
      - delay: "00:30:00"  # let the hotend/bed cool
      - service: switch.turn_off
        target:
          entity_id: switch.printer_plug
```

## Preheat from Home Assistant (new-API printers)

The `number` entities set the target temperatures:

```yaml
script:
  preheat_pla:
    alias: "Preheat for PLA"
    sequence:
      - service: number.set_value
        target:
          entity_id: number.creator_5_nozzle_target
        data:
          value: 210
      - service: number.set_value
        target:
          entity_id: number.creator_5_bed_target
        data:
          value: 60
```
