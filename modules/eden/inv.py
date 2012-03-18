# -*- coding: utf-8 -*-

""" Sahana Eden Inventory Model

    @copyright: 2009-2012 (c) Sahana Software Foundation
    @license: MIT

    Permission is hereby granted, free of charge, to any person
    obtaining a copy of this software and associated documentation
    files (the "Software"), to deal in the Software without
    restriction, including without limitation the rights to use,
    copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the
    Software is furnished to do so, subject to the following
    conditions:

    The above copyright notice and this permission notice shall be
    included in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
    EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
    OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
    NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
    HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
    WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
    FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
    OTHER DEALINGS IN THE SOFTWARE.
"""

__all__ = ["S3InventoryModel",
           "S3TrackingModel",
           "S3AdjustModel",
           "inv_tabs",
           "inv_warehouse_rheader",
           "inv_recv_crud_strings",
           "inv_recv_rheader",
           "inv_send_rheader",
           "inv_recv_rheader",
           "inv_ship_status",
           "inv_adj_rheader",
          ]

from gluon import *
from gluon.sqlhtml import RadioWidget
from gluon.storage import Storage
from ..s3 import *

SHIP_STATUS_IN_PROCESS = 0
SHIP_STATUS_RECEIVED   = 1
SHIP_STATUS_SENT       = 2
SHIP_STATUS_CANCEL     = 3

# To pass to global scope
inv_ship_status = {
                    "IN_PROCESS" : SHIP_STATUS_IN_PROCESS,
                    "RECEIVED"   : SHIP_STATUS_RECEIVED,
                    "SENT"       : SHIP_STATUS_SENT,
                    "CANCEL"     : SHIP_STATUS_CANCEL,
                }

T = current.T
shipment_status = { SHIP_STATUS_IN_PROCESS: T("In Process"),
                    SHIP_STATUS_RECEIVED:   T("Received"),
                    SHIP_STATUS_SENT:       T("Sent"),
                    SHIP_STATUS_CANCEL:     T("Canceled") }

SHIP_DOC_PENDING  = 0
SHIP_DOC_COMPLETE = 1

tn_label = T("Tracking Number")
# =============================================================================
class S3InventoryModel(S3Model):
    """
        Inventory Management

        A module to record inventories of items at a location (site)
    """

    names = ["inv_inv_item",
             "inv_item_id",
             "inv_item_represent",
             "inv_prep",
            ]

    def model(self):

        T = current.T
        db = current.db
        auth = current.auth
        s3 = current.response.s3
        settings = current.deployment_settings

        org_id = self.org_organisation_id
        item_id = self.supply_item_entity_id
        supply_item_id = self.supply_item_id
        item_pack_id = self.supply_item_pack_id
        currency_type = s3.currency_type

        org_site_represent = self.org_site_represent

        item_pack_virtualfields = self.supply_item_pack_virtualfields

        s3_date_format = settings.get_L10n_date_format()
        s3_date_represent = lambda dt: S3DateTime.date_represent(dt, utc=True)

        # =====================================================================
        # Inventory Item
        #
        tablename = "inv_inv_item"
        table = self.define_table(tablename,
                                  self.super_link("site_id",
                                                  "org_site",
                                                  label = T("Warehouse"),
                                                  default = auth.user.site_id if auth.is_logged_in() else None,
                                                  readable = True,
                                                  writable = True,
                                                  empty = False,
                                                  # Comment these to use a Dropdown & not an Autocomplete
                                                  #widget = S3SiteAutocompleteWidget(),
                                                  #comment = DIV(_class="tooltip",
                                                  #              _title="%s|%s" % (T("Inventory"),
                                                  #                                T("Enter some characters to bring up a list of possible matches"))),
                                                  represent=org_site_represent),
                                  item_id,
                                  supply_item_id(),
                                  item_pack_id(),
                                  Field("quantity",
                                        "double",
                                        label = T("Quantity"),
                                        notnull = True,
                                        writable = False),
                                  Field("pack_value",
                                        "double",
                                        label = T("Value per Pack")),
                                  # @ToDo: Move this into a Currency Widget for the pack_value field
                                  currency_type("currency"),
                                  #Field("pack_quantity",
                                  #      "double",
                                  #      compute = record_pack_quantity), # defined in 06_supply
                                  Field("expiry_date", "date",
                                        label = T("Expiry Date"),
                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
                                        represent = s3_date_represent,
                                        widget = S3DateWidget()
                                        ),
                                  Field("bin",
                                        "string",
                                        length = 16,
                                        ),
                                  Field("tracking_no",
                                        "string",
                                        length = 16,
                                        label = tn_label,
                                        ),
                                  org_id(name = "supply_org_id",
                                         label = "Supplying Organisation"), # original donating org
                                  # @ToDo: Allow items to be marked as 'still on the shelf but allocated to an outgoing shipment'
                                  #Field("status"),
                                  s3.comments(),
                                  *s3.meta_fields())

        table.virtualfields.append(item_pack_virtualfields(tablename=tablename))
        table.virtualfields.append(InvItemVirtualFields())

        # CRUD strings
        INV_ITEM = T("Warehouse Stock")
        ADD_INV_ITEM = T("Add Stock to Warehouse")
        LIST_INV_ITEMS = T("List Stock in Warehouse")
        s3.crud_strings[tablename] = Storage(
            title_create = ADD_INV_ITEM,
            title_display = T("Warehouse Stock Details"),
            title_list = LIST_INV_ITEMS,
            title_update = T("Edit Warehouse Stock"),
            title_search = T("Search Warehouse Stock"),
            title_upload = T("Import Warehouse Stock"),
            subtitle_create = ADD_INV_ITEM,
            subtitle_list = T("Warehouse Stock"),
            label_list_button = LIST_INV_ITEMS,
            label_create_button = ADD_INV_ITEM,
            label_delete_button = T("Remove Stock from Warehouse"),
            msg_record_created = T("Stock added to Warehouse"),
            msg_record_modified = T("Warehouse Stock updated"),
            msg_record_deleted = T("Stock removed from Warehouse"),
            msg_list_empty = T("No Stock currently registered in this Warehouse"))

        # Reusable Field
        inv_item_id = S3ReusableField("inv_item_id", db.inv_inv_item,
                                      requires = IS_ONE_OF(db,
                                                           "inv_inv_item.id",
                                                           self.inv_item_represent,
                                                           orderby="inv_inv_item.id",
                                                           sort=True),
                                      represent = self.inv_item_represent,
                                      label = INV_ITEM,
                                      comment = DIV( _class="tooltip",
                                                     _title="%s|%s" % (INV_ITEM,
                                                                       T("Select Stock from this Warehouse"))),
                                      ondelete = "CASCADE",
                                      script = SCRIPT("""
$(document).ready(function() {
    S3FilterFieldChange({
        'FilterField':    'inv_item_id',
        'Field':          'item_pack_id',
        'FieldResource':  'item_pack',
        'FieldPrefix':    'supply',
        'url':             S3.Ap.concat('/inv/inv_item_packs/'),
        'msgNoRecords':    S3.i18n.no_packs,
        'fncPrep':         fncPrepItem,
        'fncRepresent':    fncRepresentItem
    });
});"""),
                                )

        report_filter = [
                         S3SearchSimpleWidget(
                             name="inv_item_search_text",
                             label=T("Search"),
                             comment=T("Search for an item by text."),
                             field=[ "item_id$name",
                                     #"item_id$category_id$name",
                                     #"site_id$name"
                                    ]
                             ),
                          S3SearchOptionsWidget(
                              name="recv_search_site",
                              label=T("Facility"),
                              field=["site_id"],
                              represent ="%(name)s",
                              comment=T("If none are selected, then all are searched."),
                              cols = 2
                              ),
                          S3SearchMinMaxWidget(
                              name="inv_item_search_expiry_date",
                              method="range",
                              label=T("Expiry Date"),
                              field=["expiry_date"]
                              )
                         ]

        # Item Search Method (Advanced Search only)
        inv_item_search = S3Search(advanced=report_filter)

        self.configure(tablename,
                       super_entity = "supply_item_entity",
                       list_fields = ["id",
                                      # This is added in req/req_item_inv_item controller
                                      #"site_id",
                                      "item_id",
                                      "quantity",
                                      "pack_value",
                                      (T("Total Value"), "total_value"),
                                      "currency"
                                      ],
                       search_method = inv_item_search,
                       report_filter = report_filter,
                       report_rows = ["item_id","currency"],
                       report_cols = ["site_id","currency"],
                       report_fact = ["quantity", (T("Total Value"), "total_value")],
                       report_method=["sum"],
                       report_groupby = self.inv_inv_item.site_id,
                       report_hide_comments = True,
                       deduplicate = self.inv_item_duplicate
                       )

        # Component
        self.add_component("inv_track_item",
                           inv_inv_item="inv_item_id")

        # ---------------------------------------------------------------------
        # Pass variables back to global scope (response.s3.*)
        #
        return Storage(
                    inv_item_id = inv_item_id,
                    inv_item_represent = self.inv_item_represent,
                    inv_prep = self.inv_prep,
                )
    # ---------------------------------------------------------------------
    @staticmethod
    def inv_prep(r):
        """
            Used in site REST controllers to Filter out items which are
            already in this inventory
        """

        if r.component:

            db = current.db
            s3db = current.s3db

            if r.component.name == "inv_item":
                table = s3db.inv_inv_item
                # Filter out items which are already in this inventory
                query = (table.site_id == r.record.site_id) & \
                        (table.deleted == False)
                inv_item_rows =  db(query).select(table.item_id)
                item_ids = [row.item_id for row in inv_item_rows]

                # Ensure that the current item CAN be selected
                if r.method == "update":
                    item_ids.remove(table[r.args[2]].item_id)
                table.item_id.requires.set_filter(not_filterby = "id",
                                                  not_filter_opts = item_ids)

            elif r.component.name == "send":
                # Default to the Search tab in the location selector
                current.response.s3.gis.tab = "search"
                if current.request.get_vars.get("select", "sent") == "incoming":
                    # Display only incoming shipments which haven't been received yet
                    filter = (s3db.inv_send.status == SHIP_STATUS_SENT)
                    #r.resource.add_component_filter("send", filter)

    # ---------------------------------------------------------------------
    @staticmethod
    def inv_item_represent(id):
        """
        """

        db = current.db
        s3db = current.s3db

        itable = s3db.inv_inv_item
        stable = s3db.supply_item
        query = (itable.id == id) & \
                (itable.item_id == stable.id)
        record = db(query).select(stable.name,
                                  limitby = (0, 1)).first()
        if record:
            return record.name
        else:
            return None

    @staticmethod
    def inv_item_duplicate(job):
        """
          Rules for finding a duplicate:
           - Look for a record with the same site,
                                             bin,
                                             supply item and,
                                             pack item
        """
        if job.tablename == "inv_inv_item":
            table = job.table
            site_id = "site_id" in job.data and job.data.site_id
            item_id = "item_id" in job.data and job.data.item_id
            pack_id = "item_pack_id" in job.data and job.data.item_pack_id
            bin = "bin" in job.data and job.data.bin
            query = (table.site_id == site_id) & \
                    (table.item_id == item_id) & \
                    (table.item_pack_id == pack_id) & \
                    (table.bin == bin)
            return duplicator(job, query)

class S3TrackingModel(S3Model):
    """
        A module to manage the shipment of inventory items
        - Sent Items
        - Received Items
        - And audit trail of the shipment process 
    """

    names = ["inv_send",
             "inv_send_represent",
             "inv_recv",
             "inv_recv_represent",
             "inv_track_item",
             ]

    def model(self):

        current.manager.load("inv_adj_item")
        T = current.T
        db = current.db
        auth = current.auth
        s3 = current.response.s3
        settings = current.deployment_settings

        person_id = self.pr_person_id
        org_id = self.org_organisation_id
        item_id = self.supply_item_id
        inv_item_id = self.inv_item_id
        item_pack_id = self.supply_item_pack_id
        currency_type = s3.currency_type
        req_item_id = self.req_item_id
        adj_item_id = self.adj_item_id

        item_pack_virtualfields = self.supply_item_pack_virtualfields

        org_site_represent = self.org_site_represent

        messages = current.messages
        NONE = messages.NONE
        UNKNOWN_OPT = messages.UNKNOWN_OPT

        s3_date_format = settings.get_L10n_date_format()
        s3_date_represent = lambda dt: S3DateTime.date_represent(dt, utc=True)

        # =====================================================================
        # Send (Outgoing / Dispatch / etc)
        #
        tablename = "inv_send"
        table = self.define_table("inv_send",
                                  person_id(name = "sender_id",
                                            label = T("Sent By"),
                                            default = auth.s3_logged_in_person(),
                                            comment = self.pr_person_comment(child="sender_id")),
                                  self.super_link("site_id",
                                                  "org_site",
                                                  label = T("From Facility"),
                                                  default = auth.user.site_id if auth.is_logged_in() else None,
                                                  readable = True,
                                                  writable = True,
                                                  represent=org_site_represent
                                                  ),
                                  Field("date",
                                        "date",
                                        label = T("Date Sent"),
                                        writable = False,
                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
                                        represent = s3_date_represent,
                                        widget = S3DateWidget()
                                        ),
                                  person_id(name = "recipient_id",
                                            label = T("To Person"),
                                            comment = self.pr_person_comment(child="recipient_id")),
                                  Field("delivery_date",
                                        "date",
                                        label = T("Est. Delivery Date"),
                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
                                        represent = s3_date_represent,
                                        widget = S3DateWidget()
                                        ),
                                  Field("to_site_id",
                                        self.org_site,
                                        label = T("To Facility"),
                                        requires = IS_ONE_OF(db,
                                                             "org_site.site_id",
                                                             lambda id: org_site_represent(id, link = False),
                                                             sort=True,
                                                             ),
                                        represent =  org_site_represent
                                       ),
                                  Field("status",
                                        "integer",
                                        requires = IS_NULL_OR(IS_IN_SET(shipment_status)),
                                        represent = lambda opt: shipment_status.get(opt, UNKNOWN_OPT),
                                        default = SHIP_STATUS_IN_PROCESS,
                                        label = T("Status"),
                                        writable = False,
                                        ),
                                  s3.comments(),
                                  *s3.meta_fields())

        # CRUD strings
        ADD_SEND = T("Send Shipment")
        LIST_SEND = T("List Sent Shipments")
        s3.crud_strings[tablename] = Storage(
            title_create = ADD_SEND,
            title_display = T("Sent Shipment Details"),
            title_list = LIST_SEND,
            title_update = T("Shipment to Send"),
            title_search = T("Search Sent Shipments"),
            subtitle_create = ADD_SEND,
            subtitle_list = T("Sent Shipments"),
            label_list_button = LIST_SEND,
            label_create_button = ADD_SEND,
            label_delete_button = T("Delete Sent Shipment"),
            msg_record_created = T("Shipment Created"),
            msg_record_modified = T("Sent Shipment updated"),
            msg_record_deleted = T("Sent Shipment canceled"),
            msg_list_empty = T("No Sent Shipments"))

        # Reusable Field
        send_id = S3ReusableField( "send_id", db.inv_send, sortby="date",
                                   requires = IS_NULL_OR(IS_ONE_OF(db,
                                                                   "inv_send.id",
                                                                   self.inv_send_represent,
                                                                   orderby="inv_send_id.date",
                                                                   sort=True)),
                                   represent = self.inv_send_represent,
                                   label = T("Send Shipment"),
                                   ondelete = "RESTRICT")

        # it shouldn't be possible for the user to delete a send item
        # unless *maybe* if it is pending and has no items referencing it
        self.configure("inv_send",
                        deletable=False,
                       )

        # Component
        self.add_component("inv_track_item",
                           inv_send="send_id")

        # Generate Consignment Note
        self.set_method(tablename,
                        method="form",
                        action=self.inv_send_form )
        
        # Redirect to the Items tabs after creation
        send_item_url = URL(f="send", args=["[id]",
                                            "track_item"])
        self.configure(tablename,
                       create_next = send_item_url,
                       update_next = send_item_url)

        # =====================================================================
        # Received (In/Receive / Donation / etc)
        #
        inv_recv_type = { 0: NONE,
                          1: T("Other Warehouse"),
                          2: T("Donation"),
                          3: T("Supplier"),
                        }
    
        ship_doc_status = { SHIP_DOC_PENDING  : T("Pending"),
                            SHIP_DOC_COMPLETE : T("Complete") }
    
        radio_widget = lambda field, value: \
                                RadioWidget().widget(field, value, cols = 2)
    
        tablename = "inv_recv"
        table = self.define_table("inv_recv",
                                  person_id(name = "sender_id",
                                            label = T("Sent By Person"),
                                            comment = self.pr_person_comment(child="sender_id"),
                                            ),
                                  Field("from_site_id",
                                        "reference org_site",
                                        label = T("From Facility"),
#                                        requires = IS_ONE_OF(db,
#                                                             "org_site.site_id",
#                                                             lambda id: org_site_represent(id, link = False),
#                                                             sort=True,
#                                                            ),
                                        represent = org_site_represent
                                        ),
                                  Field("eta", "date",
                                        label = T("Date Expected"),
                                        writable = False,
                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
                                        represent = s3_date_represent,
                                        widget = S3DateWidget()
                                        ),
                                  person_id(name = "recipient_id",
                                            label = T("Received By"),
                                            default = auth.s3_logged_in_person(),
                                            comment = self.pr_person_comment(child="recipient_id")),
                                  Field("site_id",
                                        "reference org_site",
#                                  self.super_link("site_id", "org_site",
                                                  label=T("By Facility"),
                                                  default = auth.user.site_id if auth.is_logged_in() else None,
                                                  readable = True,
                                                  writable = True,
                                                  widget = S3SiteAutocompleteWidget(),
                                                  represent=org_site_represent),
                                  Field("date", "date",
                                        label = T("Date Received"),
                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
                                        represent = s3_date_represent,
                                        widget = S3DateWidget(),
                                        comment = DIV(_class="tooltip",
                                                      _title="%s|%s" % (T("Date Received"),
                                                                        T("Will be filled automatically when the Shipment has been Received"))
                                                      )
                                        ),
                                  Field("type",
                                        "integer",
                                        requires = IS_NULL_OR(IS_IN_SET(inv_recv_type)),
                                        represent = lambda opt: inv_recv_type.get(opt, UNKNOWN_OPT),
                                        label = T("Type"),
                                        default = 0,
                                        ),
                                  Field("status",
                                        "integer",
                                        requires = IS_NULL_OR(IS_IN_SET(shipment_status)),
                                        represent = lambda opt: shipment_status.get(opt, UNKNOWN_OPT),
                                        default = SHIP_STATUS_IN_PROCESS,
                                        label = T("Status"),
                                        writable = False,
                                        ),
                                  Field("grn_status",
                                        "integer",
                                        requires = IS_NULL_OR(IS_IN_SET(ship_doc_status)),
                                        represent = lambda opt: ship_doc_status.get(opt, UNKNOWN_OPT),
                                        default = SHIP_DOC_PENDING,
                                        widget = radio_widget,
                                        label = T("GRN Status"),
                                        comment = DIV( _class="tooltip",
                                                       _title="%s|%s" % (T("GRN Status"),
                                                                         T("Has the GRN (Goods Received Note) been completed?"))),
                                        ),
                                  Field("cert_status",
                                        "integer",
                                        requires = IS_NULL_OR(IS_IN_SET(ship_doc_status)),
                                        represent = lambda opt: ship_doc_status.get(opt, UNKNOWN_OPT),
                                        default = SHIP_DOC_PENDING,
                                        widget = radio_widget,
                                        label = T("Certificate Status"),
                                        comment = DIV( _class="tooltip",
                                                       _title="%s|%s" % (T("Certificate Status"),
                                                                         T("Has the Certificate for receipt of the shipment been given to the sender?"))),
                                        ),
                                  s3.comments(),
                                  *s3.meta_fields())


        # CRUD Strings
        inv_recv_crud_strings()
        if settings.get_inv_shipment_name() == "order":
            recv_id_label = T("Order")
        else:
            recv_id_label = T("Receive Shipment")

        # Reusable Field
        recv_id = S3ReusableField("recv_id", db.inv_recv, sortby="date",
                                  requires = IS_NULL_OR(IS_ONE_OF(db,
                                                                  "inv_recv.id",
                                                                  self.inv_recv_represent,
                                                                  orderby="inv_recv.date",
                                                                  sort=True)),
                                  represent = self.inv_recv_represent,
                                  label = recv_id_label,
                                  ondelete = "RESTRICT")
    
        # Search Method
        if settings.get_inv_shipment_name() == "order":
            recv_search_comment = T("Search for an order by looking for text in any field.")
            recv_search_date_field = "eta"
            recv_search_date_comment = T("Search for an order expected between these dates")
        else:
            recv_search_comment = T("Search for a shipment by looking for text in any field.")
            recv_search_date_field = "date"
            recv_search_date_comment = T("Search for a shipment received between these dates")
        recv_search = S3Search(
            simple=(S3SearchSimpleWidget(
                        name="recv_search_text_simple",
                        label=T("Search"),
                        comment=recv_search_comment,
                        field=[ "from_person",
                                "comments",
                                "from_site_id$name",
                                "recipient_id$first_name",
                                "recipient_id$middle_name",
                                "recipient_id$last_name",
                                "site_id$name"
                                ]
                      )),
            advanced=(S3SearchSimpleWidget(
                        name="recv_search_text_advanced",
                        label=T("Search"),
                        comment=recv_search_comment,
                        field=[ "from_person",
                                "comments",
                                "from_site_id$name",
                                "recipient_id$first_name",
                                "recipient_id$middle_name",
                                "recipient_id$last_name",
                                "site_id$name"
                                ]
                      ),
                      S3SearchMinMaxWidget(
                        name="recv_search_date",
                        method="range",
                        label=table[recv_search_date_field].label,
                        comment=recv_search_date_comment,
                        field=[recv_search_date_field]
                      ),
                      S3SearchOptionsWidget(
                        name="recv_search_site",
                        label=T("Facility"),
                        field=["site_id"],
                        represent ="%(name)s",
                        cols = 2
                      ),
                      S3SearchOptionsWidget(
                        name="recv_search_status",
                        label=T("Status"),
                        field=["status"],
                        cols = 2
                      ),
                      S3SearchOptionsWidget(
                        name="recv_search_grn",
                        label=T("GRN Status"),
                        field=["grn_status"],
                        cols = 2
                      ),
                      S3SearchOptionsWidget(
                        name="recv_search_cert",
                        label=T("Certificate Status"),
                        field=["grn_status"],
                        cols = 2
                      ),
            ))
    
        # Redirect to the Items tabs after creation
        recv_item_url = URL(f="recv", args=["[id]",
                                            "track_item"])

        # it shouldn't be possible for the user to delete a send item
        self.configure("inv_recv",
                        deletable=False,
                       )

        self.configure(tablename,
                       search_method = recv_search,
                       create_next = recv_item_url,
                       update_next = recv_item_url)
        # Component
        self.add_component("inv_track_item",
                           inv_recv="recv_id")
    
        # Print Forms
        self.set_method(tablename,
                        method="form",
                        action=self.inv_recv_form)
    
        self.set_method(tablename,
                        method="cert",
                        action=self.inv_recv_donation_cert )


        # =====================================================================
        # Tracking Items
        #
        tracking_status = {0 : T("Unknown"),
                           1 : T("Preparing"),
                           2 : T("In transit"),
                           3 : T("Arrived"),
                           4 : T("Canceled"),
                           }

        # @todo add the optional adj_id
        tablename = "inv_track_item"
        table = self.define_table("inv_track_item",
                                  org_id(name = "track_org_id",
                                         label = T("Shipping Organization"),
                                         ondelete = "NO ACTION",
                                         readable = False,
                                         writable = False),
                                  Field("tracking_no",
                                        "string",
                                        length = 16,
                                        required = True,
                                        label = tn_label,
                                        ),
                                  Field("status",
                                        "integer",
                                        required = True,
                                        requires = IS_IN_SET(tracking_status),
                                        default = 1,
                                        represent = lambda opt: tracking_status[opt],
                                        writable = False),
                                  inv_item_id(name="send_stock_id",
                                              ondelete = "NO ACTION",
                                              script = SCRIPT("""
$(document).ready(function() {
    S3FilterFieldChange({
        'FilterField':    'send_stock_id',
        'Field':          'item_pack_id',
        'FieldResource':  'item_pack',
        'FieldPrefix':    'supply',
        'url':             S3.Ap.concat('/inv/inv_item_packs/'),
        'msgNoRecords':    S3.i18n.no_packs,
        'fncPrep':         fncPrepItem,
        'fncRepresent':    fncRepresentItem
    });
});""") # need to redefine the script because of the change in the field name :/
                                ),  # original inventory
                                  item_id(ondelete = "NO ACTION"),      # supply item
                                  item_pack_id(ondelete = "NO ACTION"), # pack table
                                  Field("quantity",
                                        "double",
                                        label = T("Quantity Sent"),
                                        notnull = True),
                                  Field("recv_quantity",
                                        "double",
                                        label = T("Quantity Received"),
                                        represent = self.qnty_recv_repr,
                                        readable = False,
                                        writable = False,),
                                  currency_type("currency"),
                                  Field("pack_value",
                                        "double",
                                        label = T("Value per Pack")),
                                  Field("expiry_date", "date",
                                        label = T("Expiry Date"),
                                        #requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
                                        represent = s3_date_represent,
                                        widget = S3DateWidget()
                                        ),
                                  Field("bin",                # The bin at origin 
                                        "string",
                                        length = 16,
                                        ),
                                  send_id(), # send record
                                  recv_id(), # receive record
                                  inv_item_id(name="recv_stock_id",
                                              label = "Receiving Inventory",
                                              required = False,
                                              readable = False,
                                              writable = False,
                                              ondelete = "NO ACTION"),  # received inventory
                                  Field("recv_bin",                # The bin at destination 
                                        "string",
                                        length = 16,
                                        readable = False,
                                        writable = False,
                                        widget = S3InvBinWidget("inv_track_item")
                                        ),
                                  org_id(name = "supply_org_id",
                                         label = "Supplying Organisation"), # original donating org
                                  adj_item_id(), # any adjustment record
                                  s3.comments(),
                                  req_item_id(readable = False,
                                              writable = False),
                                  *s3.meta_fields()
                                  )
    
        # pack_quantity virtual field
        table.virtualfields.append(item_pack_virtualfields(tablename=tablename))

        # CRUD strings
        ADD_SEND_ITEM = T("Add Item to Shipment")
        LIST_SEND_ITEMS = T("List Sent Items")
        s3.crud_strings[tablename] = Storage(
            title_create = ADD_SEND_ITEM,
            title_display = T("Sent Item Details"),
            title_list = LIST_SEND_ITEMS,
            title_update = T("Edit Sent Item"),
            title_search = T("Search Sent Items"),
            subtitle_create = T("Add New Sent Item"),
            subtitle_list = T("Shipment Items"),
            label_list_button = LIST_SEND_ITEMS,
            label_create_button = ADD_SEND_ITEM,
            label_delete_button = T("Delete Sent Item"),
            msg_record_created = T("Item Added to Shipment"),
            msg_record_modified = T("Sent Item updated"),
            msg_record_deleted = T("Sent Item deleted"),
            msg_list_empty = T("No Sent Items currently registered"))

        # Update owned_by_role to the send's owned_by_role
        self.configure(tablename,
                       onaccept = self.inv_track_item_onaccept,
                       onvalidation = self.inv_track_item_onvalidate,
                       )

        # ---------------------------------------------------------------------
        # Pass variables back to global scope (response.s3.*)
        #
        return Storage(inv_track_item_deleting = self.inv_track_item_deleting,
                       inv_track_item_unload = self.inv_track_item_unload,
                      )

    # ---------------------------------------------------------------------
    @staticmethod
    def inv_send_represent(id):
        """
        """

        if id:

            db = current.db
            s3db = current.s3db

            table = s3db.inv_send
            send_row = db(table.id == id).select(table.date,
                                                 table.to_site_id,
                                                 limitby=(0, 1)).first()
            return SPAN(table.to_site_id.represent(send_row.to_site_id),
                        " - ",
                        table.date.represent(send_row.date)
                        )
        else:
            return current.messages.NONE

    # ---------------------------------------------------------------------
    @staticmethod
    def inv_send_form (r, **attr):
        """
            Generate a PDF of a Consignment Note
        """

        s3db = current.s3db

        table = s3db.inv_send
        tracktable = s3db.inv_track_item
        table.date.readable = True

        record = table[r.id]
        site_id = record.site_id
        site = table.site_id.represent(site_id,False)
        # hide the inv_item field
        tracktable.send_stock_id.readable = False
        tracktable.recv_stock_item.readable = False

        exporter = S3PDF()
        return exporter(r,
                        method="list",
                        componentname="inv_track_item",
                        formname="Waybill",
                        filename="Waybill-%s" % site,
                        report_hide_comments=True,
                        **attr
                       )

    # ---------------------------------------------------------------------
    @staticmethod
    def inv_recv_represent(id):
        """
            @ToDo: 'From Organisation' is great for Donations
            (& Procurement if we make Suppliers Organisations), but isn't useful
            for shipments between facilities within a single Org where
            'From Facility' could be more appropriate
        """
        if id:

            db = current.db
            s3db = current.s3db

            table = s3db.inv_recv
            inv_recv_row = db(table.id == id).select(table.date,
                                                     table.from_site_id,
                                                     limitby=(0, 1)).first()
            return SPAN(table.from_site_id.represent(inv_recv_row.from_site_id),
                        " - ",
                        table.date.represent(inv_recv_row.date)
                        )
        else:
            return current.messages.NONE

    # ---------------------------------------------------------------------
    @staticmethod
    def inv_recv_form (r, **attr):
        """
            Generate a PDF of a GRN (Goods Received Note)
        """

        T = current.T
        s3db = current.s3db

        table = s3db.inv_recv
        table.date.readable = True
        table.site_id.readable = True
        table.site_id.label = T("By Warehouse")
        table.site_id.represent = s3db.org_site_represent

        record = table[r.id]
        site_id = record.site_id
        site = table.site_id.represent(site_id,False)

        exporter = S3PDF()
        return exporter(r,
                        method="list",
                        formname="Goods Received Note",
                        filename="GRN-%s" % site,
                        report_hide_comments=True,
                        componentname = "inv_track_item",
                        **attr
                       )

    # -------------------------------------------------------------------------
    @staticmethod
    def inv_recv_donation_cert (r, **attr):
        """
            Generate a PDF of a Donation certificate
        """

        s3db = current.s3db

        table = s3db.inv_recv
        table.date.readable = True
        table.type.readable = False
        table.site_id.readable = True
        table.site_id.label = T("By Warehouse")
        table.site_id.represent = s3db.org_site_represent

        record = table[r.id]
        site_id = record.site_id
        site = table.site_id.represent(site_id,False)

        exporter = S3PDF()
        return exporter(r,
                        method="list",
                        formname="Donation Certificate",
                        filename="DC-%s" % site,
                        report_hide_comments=True,
                        componentname = "inv_track_item",
                        **attr
                       )

    # -------------------------------------------------------------------------
    @staticmethod
    def qnty_recv_repr(value):
        if value:
            return value
        else:
            return B(value)

    # -------------------------------------------------------------------------
    @staticmethod
    def inv_track_item_onvalidate(form):
        """
            When a track item record is being created with a tracking number
            then the tracking number needs to be unique within the organisation.

            If the stock is coming out of a warehouse then the stock details
            need to be copied across (org, expiry etc)

            If the stock is being received then their might be a selected bin
            ensure that the correct bin is selected and save those details.
        """
        s3db = current.s3db
        db = current.db
        ttable = s3db.inv_track_item
        itable = s3db.inv_inv_item
        stable = s3db.org_site

        # save the organisation from where this tracking originates
        if form.vars.send_stock_id:
            query = (itable.id == form.vars.send_stock_id) & \
                    (itable.site_id == stable.id)
            record = db(query).select(stable.organisation_id,
                                      limitby=(0, 1)).first()

            form.vars.track_org_id = record.organisation_id
        # If their is a tracking number check that it is unique within the org
        if form.vars.tracking_no:
            if form.record.tracking_no and form.record.tracking_no == form.vars.tracking_no:
                # the tracking number hasn't changes so no validation needed
                pass
            else:
                org_repr = current.response.s3.org_organisation_represent
                query = (ttable.track_org_id == form.vars.track_org_id) & \
                        (ttable.tracking_no == form.vars.tracking_no)
                record = db(query).select(limitby=(0, 1)).first()
                if record:
                    form.errors.tracking_no = T("The Tracking Number %s is already used by %s.") % (form.vars.tracking_no,
                                                                                                    org_repr(record.track_org_id))

        # copy the data from the donated stock
        if form.vars.send_stock_id:
            query = (itable.id == form.vars.send_stock_id)
            record = db(query).select(limitby=(0, 1)).first()
            form.vars.item_id = record.item_id
            form.vars.expiry_date = record.expiry_date
            form.vars.bin = record.bin
            form.vars.supply_org_id = record.supply_org_id

        # If their is a receiving bin select the right one
        if form.vars.recv_bin:
            if isinstance(form.vars.recv_bin, list):
                if form.vars.recv_bin[1] != "":
                    form.vars.recv_bin = form.vars.recv_bin[1]
                else:
                    form.vars.recv_bin = form.vars.recv_bin[0]
        return

    @staticmethod
    def inv_track_item_onaccept(form):
        """
           When a track item record is created and it is linked to an inv_item
           then the inv_item quantity will be reduced.
        """
        s3db = current.s3db
        db = current.db
        table = s3db.inv_inv_item
        oldTotal = 0
        # only modify the original stock total if we have a quantity on the form
        # Their'll not be one if it is being received since by then it is read only
        if form.vars.quantity:
            if form.record:
                if form.record.send_stock_id != None:
                    oldTotal = form.record.quantity
                    db(table.id == form.record.send_stock_id).update(quantity = table.quantity + oldTotal)
            newTotal = form.vars.quantity
            db(table.id == form.vars.send_stock_id).update(quantity = table.quantity - newTotal)

    @staticmethod
    def inv_track_item_deleting(id):
        """
           A track item can only be deleted if the status is Preparing
           When a track item record is deleted and it is linked to an inv_item
           then the inv_item quantity will be reduced.
        """
        s3db = current.s3db
        db = current.db
        tracktable = s3db.inv_track_item
        stocktable = s3db.inv_inv_item
        record = tracktable[id]
        if record.status != 1:
            return False
        # Check that we have a link to a warehouse
        if record.send_stock_id:
            trackTotal = record.quantity
            # Remove the total from this record and place it back in the warehouse
            db(stocktable.id == record.send_stock_id).update(quantity = stocktable.quantity + trackTotal)
            db(tracktable.id == id).update(quantity = 0,
                                           comments = "%sQuantity was: %s" % (stocktable.comments, trackTotal))
        return True

    @staticmethod
    def inv_track_item_unload(id, site_id, adj_id):
        """
            Find a inv_item with the same bin (if provided) or create a new one
            and then increment the total.
            
            If the send and recv values differ then create an adjustment record
            
            Add the inv_item reference to the track_item record
        """
        s3db = current.s3db
        db = current.db
        tracktable = s3db.inv_track_item
        stocktable = s3db.inv_inv_item
        record = tracktable[id]
        query = (stocktable.item_id == record.item_id) & \
                (stocktable.item_pack_id == record.item_pack_id) & \
                (stocktable.currency == record.currency) & \
                (stocktable.pack_value == record.pack_value) & \
                (stocktable.expiry_date == record.expiry_date) & \
                (stocktable.bin == record.recv_bin) & \
                (stocktable.supply_org_id == record.supply_org_id)
        inv_item_row = db(query).select(stocktable.id,
                                        limitby=(0, 1)).first()
        if inv_item_row:
            stock_id = inv_item_row.id
            db(stocktable.id == stock_id).update(quantity = stocktable.quantity + record.recv_quantity)
        else:
            stock_id = stocktable.insert(site_id = site_id,
                                         item_id = record.item_id,
                                         item_pack_id = record.item_pack_id,
                                         currency = record.currency,
                                         pack_value = record.pack_value,
                                         expiry_date = record.expiry_date,
                                         bin = record.recv_bin,
                                         supply_org_id = record.supply_org_id,
                                         quantity = record.recv_quantity,
                                         tracking_no = record.tracking_no,
                                        )
        db(tracktable.id == id).update(recv_stock_id = stock_id)
        # If the receive quantity doesn't equal the sent quantity
        # then an adjustment needs to be set up
        if record.quantity != record.recv_quantity:
            # If we don't yet have an adj record then create it
            if adj_id == None:
                adjtable = s3db.inv_adj
                recv_rec = s3db.inv_recv[record.recv_id]
                adj_id = adjtable.insert(adjuster_id = recv_rec.recipient_id,
                                         site_id = recv_rec.site_id,
                                         adjustment_date = current.request.now.date(),
                                         category = 0,
                                         status = 1,
                                         comments = recv_rec.comments,
                                        )
            # Now create the adi item record
            adjitemtable = s3db.inv_adj_item
            adj_item_id = adjitemtable.insert(reason = 0,
                                              adj_id = adj_id,
                                              inv_item_id = record.send_stock_id, # original source inv_item
                                              item_id = record.item_id, # the supply item
                                              item_pack_id = record.item_pack_id,
                                              old_quantity = record.quantity,
                                              new_quantity = record.recv_quantity,
                                              currency = record.currency,
                                              pack_value = record.pack_value,
                                              expiry_date = record.expiry_date,
                                              bin = record.recv_bin,
                                              comments = record.comments,
                                              )
            # copy the adj_item_id to the tracking record
            db(tracktable.id == id).update(adj_item_id = adj_item_id)

## =============================================================================
#class S3IncomingModel(S3Model):
#    """
#        A module to record Incoming items to an Inventory:
#        - Donations, Purchases, Stock Transfers
#    """
#
#    names = ["inv_recv",
#             "inv_recv_item",
#            ]
#
#    def model(self):
#
#        T = current.T
#        db = current.db
#        auth = current.auth
#        s3 = current.response.s3
#        settings = current.deployment_settings
#
#        person_id = self.pr_person_id
#        #location_id = self.gis_location_id
#        #organisation_id = self.org_organisation_id
#        #organisation_represent = self.org_organisation_represent
#        org_site_represent = self.org_site_represent
#        item_id = self.supply_item_entity_id
#        supply_item_id = self.supply_item_id
#        item_pack_id = self.supply_item_pack_id
#        item_pack_virtualfields = self.supply_item_pack_virtualfields
#        req_item_id = self.req_item_id
#
#        messages = current.messages
#        NONE = messages.NONE
#        UNKNOWN_OPT = messages.UNKNOWN_OPT
#
#        s3_date_format = settings.get_L10n_date_format()
#        s3_date_represent = lambda dt: S3DateTime.date_represent(dt, utc=True)
#
#        # =====================================================================
#        # Received (In/Receive / Donation / etc)
#        #
#        inv_recv_type = { 0: NONE,
#                          1: T("Other Warehouse"),
#                          2: T("Donation"),
#                          3: T("Supplier"),
#                        }
#
#        ship_doc_status = { SHIP_DOC_PENDING  : T("Pending"),
#                            SHIP_DOC_COMPLETE : T("Complete") }
#
#        radio_widget = lambda field, value: \
#                                RadioWidget().widget(field, value, cols = 2)
#
#        tablename = "inv_recv"
#        table = self.define_table(tablename,
#                                  Field("eta", "date",
#                                        label = T("Date Expected"),
#                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
#                                        represent = s3_date_represent,
#                                        widget = S3DateWidget()
#                                        ),
#                                  Field("date", "date",
#                                        label = T("Date Received"),
#                                        writable = False,
#                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
#                                        represent = s3_date_represent,
#                                        widget = S3DateWidget(),
#                                        comment = DIV(_class="tooltip",
#                                                      _title="%s|%s" % (T("Date Received"),
#                                                                        T("Will be filled automatically when the Shipment has been Received"))
#                                                      )
#                                        #readable = False # unless the record is locked
#                                        ),
#                                  Field("type",
#                                        "integer",
#                                        requires = IS_NULL_OR(IS_IN_SET(inv_recv_type)),
#                                        represent = lambda opt: inv_recv_type.get(opt, UNKNOWN_OPT),
#                                        label = T("Type"),
#                                        default = 0,
#                                        ),
#                                  person_id(name = "recipient_id",
#                                            label = T("Received By"),
#                                            default = auth.s3_logged_in_person(),
#                                            comment = self.pr_person_comment(child="recipient_id")),
#                                  self.super_link("site_id", "org_site",
#                                                  label=T("By Facility"),
#                                                  default = auth.user.site_id if auth.is_logged_in() else None,
#                                                  readable = True,
#                                                  writable = True,
#                                                  # Comment these to use a Dropdown & not an Autocomplete
#                                                  #widget = S3SiteAutocompleteWidget(),
#                                                  #comment = DIV(_class="tooltip",
#                                                  #              _title="%s|%s" % (T("By Inventory"),
#                                                  #                                T("Enter some characters to bring up a list of possible matches"))),
#                                                  represent=org_site_represent),
#                                  Field("from_site_id",
#                                        self.org_site,
#                                        label = T("From Facility"),
#                                        requires = IS_ONE_OF(db,
#                                                             "org_site.site_id",
#                                                             lambda id: org_site_represent(id, link = False),
#                                                             sort=True,
#                                                            ),
#                                        represent = org_site_represent
#                                        ),
#                                  #location_id("from_location_id",
#                                  #            label = T("From Location")),
#                                  #organisation_id(#"from_organisation_id",
#                                  #                label = T("From Organization"),
#                                                  #comment = from_organisation_comment
#                                  #                comment = organisation_comment),
#                                  #Field("from_person"), # Text field, because lookup to pr_person record is unnecessarily complex workflow
#                                  person_id(name = "sender_id",
#                                            label = T("Sent By Person"),
#                                            comment = self.pr_person_comment(child="sender_id"),
#                                            ),
#                                  Field("status",
#                                        "integer",
#                                        requires = IS_NULL_OR(IS_IN_SET(shipment_status)),
#                                        represent = lambda opt: shipment_status.get(opt, UNKNOWN_OPT),
#                                        default = SHIP_STATUS_IN_PROCESS,
#                                        label = T("Status"),
#                                        writable = False,
#                                        ),
#                                  Field("grn_status",
#                                        "integer",
#                                        requires = IS_NULL_OR(IS_IN_SET(ship_doc_status)),
#                                        represent = lambda opt: ship_doc_status.get(opt, UNKNOWN_OPT),
#                                        default = SHIP_DOC_PENDING,
#                                        widget = radio_widget,
#                                        label = T("GRN Status"),
#                                        comment = DIV( _class="tooltip",
#                                                       _title="%s|%s" % (T("GRN Status"),
#                                                                         T("Has the GRN (Goods Received Note) been completed?"))),
#                                        ),
#                                  Field("cert_status",
#                                        "integer",
#                                        requires = IS_NULL_OR(IS_IN_SET(ship_doc_status)),
#                                        represent = lambda opt: ship_doc_status.get(opt, UNKNOWN_OPT),
#                                        default = SHIP_DOC_PENDING,
#                                        widget = radio_widget,
#                                        label = T("Certificate Status"),
#                                        comment = DIV( _class="tooltip",
#                                                       _title="%s|%s" % (T("Certificate Status"),
#                                                                         T("Has the Certificate for receipt of the shipment been given to the sender?"))),
#                                        ),
#                                  s3.comments(),
#                                  *s3.meta_fields())
#
#        # Reusable Field
#        if settings.get_inv_shipment_name() == "order":
#            recv_id_label = T("Order")
#        else:
#            recv_id_label = T("Receive Shipment")
#        recv_id = S3ReusableField("recv_id", db.inv_recv, sortby="date",
#                                  requires = IS_NULL_OR(IS_ONE_OF(db,
#                                                                  "inv_recv.id",
#                                                                  self.inv_recv_represent,
#                                                                  orderby="inv_recv.date",
#                                                                  sort=True)),
#                                  represent = self.inv_recv_represent,
#                                  label = recv_id_label,
#                                  #comment = DIV(A(ADD_DISTRIBUTION, _class="colorbox", _href=URL(c="inv", f="distrib", args="create", vars=dict(format="popup")), _target="top", _title=ADD_DISTRIBUTION),
#                                  #          DIV( _class="tooltip", _title=T("Distribution") + "|" + T("Add Distribution."))),
#                                  ondelete = "CASCADE")
#
#        # Search Method
#        if settings.get_inv_shipment_name() == "order":
#            recv_search_comment = T("Search for an order by looking for text in any field.")
#            recv_search_date_field = "eta"
#            recv_search_date_comment = T("Search for an order expected between these dates")
#        else:
#            recv_search_comment = T("Search for a shipment by looking for text in any field.")
#            recv_search_date_field = "date"
#            recv_search_date_comment = T("Search for a shipment received between these dates")
#        recv_search = S3Search(
#            simple=(S3SearchSimpleWidget(
#                        name="recv_search_text_simple",
#                        label=T("Search"),
#                        comment=recv_search_comment,
#                        field=[ "from_person",
#                                "comments",
#                                #"organisation_id$name",
#                                #"organisation_id$acronym",
#                                "from_site_id$name",
#                                "recipient_id$first_name",
#                                "recipient_id$middle_name",
#                                "recipient_id$last_name",
#                                "site_id$name"
#                                ]
#                      )),
#            advanced=(S3SearchSimpleWidget(
#                        name="recv_search_text_advanced",
#                        label=T("Search"),
#                        comment=recv_search_comment,
#                        field=[ "from_person",
#                                "comments",
#                                #"organisation_id$name",
#                                #"organisation_id$acronym",
#                                "from_site_id$name",
#                                "recipient_id$first_name",
#                                "recipient_id$middle_name",
#                                "recipient_id$last_name",
#                                "site_id$name"
#                                ]
#                      ),
#                      S3SearchMinMaxWidget(
#                        name="recv_search_date",
#                        method="range",
#                        label=table[recv_search_date_field].label,
#                        comment=recv_search_date_comment,
#                        field=[recv_search_date_field]
#                      ),
#                      S3SearchOptionsWidget(
#                        name="recv_search_site",
#                        label=T("Facility"),
#                        field=["site_id"],
#                        represent ="%(name)s",
#                        cols = 2
#                      ),
#                      S3SearchOptionsWidget(
#                        name="recv_search_status",
#                        label=T("Status"),
#                        field=["status"],
#                        cols = 2
#                      ),
#                      S3SearchOptionsWidget(
#                        name="recv_search_grn",
#                        label=T("GRN Status"),
#                        field=["grn_status"],
#                        cols = 2
#                      ),
#                      S3SearchOptionsWidget(
#                        name="recv_search_cert",
#                        label=T("Certificate Status"),
#                        field=["grn_status"],
#                        cols = 2
#                      ),
#            ))
#
#        # Redirect to the Items tabs after creation
#        recv_item_url = URL(f="recv", args=["[id]",
#                                            "recv_item"])
#
#        self.configure(tablename,
#                       search_method = recv_search,
#                       create_next = recv_item_url,
#                       update_next = recv_item_url)
#        # Component
#        self.add_component("inv_recv_item",
#                           inv_recv="recv_id")
#
#        # Print Forms
#        self.set_method(tablename,
#                        method="form",
#                        action=self.inv_recv_form)
#
#        self.set_method(tablename,
#                        method="cert",
#                        action=self.inv_recv_donation_cert )
#
#        # =====================================================================
#        # In (Receive / Donation / etc) Items
#        #
#        tablename = "inv_recv_item"
#        table = self.define_table(tablename,
#                                  recv_id(),
#                                  item_id,
#                                  supply_item_id(),
#                                  item_pack_id(),
#                                  Field("quantity", "double",
#                                        label = T("Quantity"),
#                                        notnull = True),
#                                  s3.comments(),
#                                  req_item_id(readable = False,
#                                              writable = False),
#                                  *s3.meta_fields())
#
#        self.configure(tablename,
#                       super_entity = "supply_item_entity")
#
#        # pack_quantity virtual field
#        table.virtualfields.append(item_pack_virtualfields(tablename=tablename))
#
#        # CRUD strings
#        if settings.get_inv_shipment_name() == "order":
#            ADD_RECV_ITEM = T("Add New Item to Order")
#            LIST_RECV_ITEMS = T("List Order Items")
#            s3.crud_strings[tablename] = Storage(
#                title_create = ADD_RECV_ITEM,
#                title_display = T("Order Item Details"),
#                title_list = LIST_RECV_ITEMS,
#                title_update = T("Edit Order Item"),
#                title_search = T("Search Order Items"),
#                subtitle_create = T("Add New Item to Order"),
#                subtitle_list = T("Order Items"),
#                label_list_button = LIST_RECV_ITEMS,
#                label_create_button = ADD_RECV_ITEM,
#                label_delete_button = T("Remove Item from Order"),
#                msg_record_created = T("Item added to order"),
#                msg_record_modified = T("Order Item updated"),
#                msg_record_deleted = T("Item removed from order"),
#                msg_list_empty = T("No Order Items currently registered"))
#        else:
#            ADD_RECV_ITEM = T("Add New Item to Shipment")
#            LIST_RECV_ITEMS = T("List Received Items")
#            s3.crud_strings[tablename] = Storage(
#                title_create = ADD_RECV_ITEM,
#                title_display = T("Received Item Details"),
#                title_list = LIST_RECV_ITEMS,
#                title_update = T("Edit Received Item"),
#                title_search = T("Search Received Items"),
#                subtitle_create = T("Add New Received Item"),
#                subtitle_list = T("Shipment Items"),
#                label_list_button = LIST_RECV_ITEMS,
#                label_create_button = ADD_RECV_ITEM,
#                label_delete_button = T("Remove Item from Shipment"),
#                msg_record_created = T("Item added to shipment"),
#                msg_record_modified = T("Received Item updated"),
#                msg_record_deleted = T("Item removed from shipment"),
#                msg_list_empty = T("No Received Items currently registered"))
#
#        # ---------------------------------------------------------------------
#        # Pass variables back to global scope (response.s3.*)
#        #
#        return Storage(
#                )
#
#    # ---------------------------------------------------------------------
#    def inv_recv_represent(id):
#        """
#            @ToDo: 'From Organisation' is great for Donations
#            (& Procurement if we make Suppliers Organisations), but isn't useful
#            for shipments between facilities within a single Org where
#            'From Facility' could be more appropriate
#        """
#
#        if id:
#
#            db = current.db
#            s3db = current.s3db
#
#            table = s3db.inv_recv
#            inv_recv_row = db(table.id == id).select(table.date,
#                                                     table.from_site_id,
#                                                     #table.organisation_id,
#                                                     limitby=(0, 1)).first()
#            return SPAN(table.from_site_id.represent(inv_recv_row.from_site_id),
#                        #"(", table.organisation_id.represent( inv_recv_row.organisation_id), ")",
#                        " - ",
#                        table.date.represent(inv_recv_row.date)
#                        )
#        else:
#            return current.messages.NONE
#
#    # ---------------------------------------------------------------------
#    @staticmethod
#    def inv_recv_form (r, **attr):
#        """
#            Generate a PDF of a GRN (Goods Received Note)
#        """
#
#        T = current.T
#        s3db = current.s3db
#
#        table = s3db.inv_recv
#        table.date.readable = True
#        table.site_id.readable = True
#        table.site_id.label = T("By Warehouse")
#        table.site_id.represent = s3db.org_site_represent
#
#        record = table[r.id]
#        site_id = record.site_id
#        site = table.site_id.represent(site_id,False)
#
#        exporter = S3PDF()
#        return exporter(r,
#                        method="list",
#                        formname="Goods Received Note",
#                        filename="GRN-%s" % site,
#                        report_hide_comments=True,
#                        componentname = "inv_recv_item",
#                        **attr
#                       )
#
#    # -------------------------------------------------------------------------
#    @staticmethod
#    def inv_recv_donation_cert (r, **attr):
#        """
#            Generate a PDF of a Donation certificate
#        """
#
#        s3db = current.s3db
#
#        table = s3db.inv_recv
#        table.date.readable = True
#        table.type.readable = False
#        table.site_id.readable = True
#        table.site_id.label = T("By Warehouse")
#        table.site_id.represent = s3db.org_site_represent
#
#        record = table[r.id]
#        site_id = record.site_id
#        site = table.site_id.represent(site_id,False)
#
#        exporter = S3PDF()
#        return exporter(r,
#                        method="list",
#                        formname="Donation Certificate",
#                        filename="DC-%s" % site,
#                        report_hide_comments=True,
#                        componentname = "inv_recv_item",
#                        **attr
#                       )
#
#
## =============================================================================
#class S3DistributionModel(S3Model):
#    """
#        Distribution Management
#
#        A module to record all Outgoing stock from an Inventory:
#        - Distributions, Stock Transfers
#    """
#
#    names = ["inv_send",
#             "inv_send_item",
#            ]
#
#    def model(self):
#
#        T = current.T
#        db = current.db
#        auth = current.auth
#        s3 = current.response.s3
#        settings = current.deployment_settings
#
#        person_id = self.pr_person_id
#        #location_id = self.gis_location_id
#        org_site_represent = self.org_site_represent
#        # @ToDo: make Sent Items an Item Entity instance
#        #item_id = self.supply_item_entity_id
#        #supply_item_id = self.supply_item_id
#        inv_item_id = self.inv_item_id
#        item_pack_id = self.supply_item_pack_id
#        item_pack_virtualfields = self.supply_item_pack_virtualfields
#        req_item_id = self.req_item_id
#
#        messages = current.messages
#        NONE = messages.NONE
#        UNKNOWN_OPT = messages.UNKNOWN_OPT
#
#        s3_date_format = settings.get_L10n_date_format()
#        s3_date_represent = lambda dt: S3DateTime.date_represent(dt, utc=True)
#
#        # =====================================================================
#        # Send (Outgoing / Dispatch / etc)
#        #
#        tablename = "inv_send"
#        table = self.define_table(tablename,
#                                  Field("date", "date",
#                                        label = T("Date Sent"),
#                                        writable = False,
#                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
#                                        represent = s3_date_represent,
#                                        widget = S3DateWidget()
#                                        ),
#                                  person_id(name = "sender_id",
#                                            label = T("Sent By"),
#                                            default = auth.s3_logged_in_person(),
#                                            comment = self.pr_person_comment(child="sender_id")),
#                                  self.super_link("site_id", "org_site",
#                                             label = T("From Facility"),
#                                             default = auth.user.site_id if auth.is_logged_in() else None,
#                                             readable = True,
#                                             writable = True,
#                                             # Comment these to use a Dropdown & not an Autocomplete
#                                             #widget = S3SiteAutocompleteWidget(),
#                                             #comment = DIV(_class="tooltip",
#                                             #              _title="%s|%s" % (T("From Warehouse"),
#                                             #                                T("Enter some characters to bring up a list of possible matches"))),
#                                            represent=org_site_represent),
#                                  Field("delivery_date", "date",
#                                        label = T("Est. Delivery Date"),
#                                        requires = IS_NULL_OR(IS_DATE(format = s3_date_format)),
#                                        represent = s3_date_represent,
#                                        widget = S3DateWidget()
#                                        ),
#                                  Field("to_site_id",
#                                        self.org_site,
#                                        label = T("To Facility"),
#                                        requires = IS_ONE_OF(db,
#                                                             "org_site.site_id",
#                                                             lambda id: org_site_represent(id, link = False),
#                                                             sort=True,
#                                                             ),
#                                        represent =  org_site_represent
#                                       ),
#                                  #location_id( "to_location_id",
#                                  #             label = T("To Location") ),
#                                  Field("status",
#                                        "integer",
#                                        requires = IS_NULL_OR(IS_IN_SET(shipment_status)),
#                                        represent = lambda opt: shipment_status.get(opt, UNKNOWN_OPT),
#                                        default = SHIP_STATUS_IN_PROCESS,
#                                        label = T("Status"),
#                                        writable = False,
#                                        ),
#                                  person_id(name = "recipient_id",
#                                            label = T("To Person"),
#                                            comment = self.pr_person_comment(child="recipient_id")),
#                                  s3.comments(),
#                                  *s3.meta_fields())
#
#        # CRUD strings
#        ADD_SEND = T("Send Shipment")
#        LIST_SEND = T("List Sent Shipments")
#        s3.crud_strings[tablename] = Storage(
#            title_create = ADD_SEND,
#            title_display = T("Sent Shipment Details"),
#            title_list = LIST_SEND,
#            title_update = T("Shipment to Send"),
#            title_search = T("Search Sent Shipments"),
#            subtitle_create = ADD_SEND,
#            subtitle_list = T("Sent Shipments"),
#            label_list_button = LIST_SEND,
#            label_create_button = ADD_SEND,
#            label_delete_button = T("Delete Sent Shipment"),
#            msg_record_created = T("Shipment Created"),
#            msg_record_modified = T("Sent Shipment updated"),
#            msg_record_deleted = T("Sent Shipment canceled"),
#            msg_list_empty = T("No Sent Shipments"))
#
#        # Reusable Field
#        send_id = S3ReusableField( "send_id", db.inv_send, sortby="date",
#                                   requires = IS_NULL_OR(IS_ONE_OF(db,
#                                                                   "inv_send.id",
#                                                                   self.inv_send_represent,
#                                                                   orderby="inv_send_id.date",
#                                                                   sort=True)),
#                                   represent = self.inv_send_represent,
#                                   label = T("Send Shipment"),
#                                   ondelete = "CASCADE")
#
#        # Component
#        self.add_component("inv_send_item",
#                           inv_send="send_id")
#
#        # Generate Consignment Note
#        self.set_method(tablename,
#                        method="form",
#                        action=self.inv_send_form )
#        
#        # Redirect to the Items tabs after creation
#        send_item_url = URL(f="send", args=["[id]",
#                                            "send_item"])
#        self.configure(tablename,
#                        create_next = send_item_url,
#                        update_next = send_item_url)
#
#        # =====================================================================
#        # Send (Outgoing / Dispatch / etc) Items
#        #
#        log_sent_item_status = { 0: NONE,
#                                 1: T("Insufficient Quantity") }
#
#        tablename = "inv_send_item"
#        table = self.define_table(tablename,
#                                  send_id(),
#                                  inv_item_id(),
#                                  item_pack_id(),
#                                  Field("quantity", "double",
#                                        label = T("Quantity"),
#                                        notnull = True),
#                                  s3.comments(),
#                                  Field("status",
#                                        "integer",
#                                        requires = IS_NULL_OR(IS_IN_SET(log_sent_item_status)),
#                                        represent = lambda opt: log_sent_item_status[opt] if opt else log_sent_item_status[0],
#                                        writable = False),
#                                  req_item_id(readable = False,
#                                              writable = False),
#                                  *s3.meta_fields())
#
#        # pack_quantity virtual field
#        table.virtualfields.append(item_pack_virtualfields(tablename=tablename))
#
#        # CRUD strings
#        ADD_SEND_ITEM = T("Add Item to Shipment")
#        LIST_SEND_ITEMS = T("List Sent Items")
#        s3.crud_strings[tablename] = Storage(
#            title_create = ADD_SEND_ITEM,
#            title_display = T("Sent Item Details"),
#            title_list = LIST_SEND_ITEMS,
#            title_update = T("Edit Sent Item"),
#            title_search = T("Search Sent Items"),
#            subtitle_create = T("Add New Sent Item"),
#            subtitle_list = T("Shipment Items"),
#            label_list_button = LIST_SEND_ITEMS,
#            label_create_button = ADD_SEND_ITEM,
#            label_delete_button = T("Delete Sent Item"),
#            msg_record_created = T("Item Added to Shipment"),
#            msg_record_modified = T("Sent Item updated"),
#            msg_record_deleted = T("Sent Item deleted"),
#            msg_list_empty = T("No Sent Items currently registered"))
#
#        # Update owned_by_role to the send's owned_by_role
#        self.configure(tablename,
#                       onaccept = self.inv_send_item_onaccept)
#
#        # ---------------------------------------------------------------------
#        # Pass variables back to global scope (response.s3.*)
#        #
#        return Storage(
#                )
#
#    # ---------------------------------------------------------------------
#    @staticmethod
#    def inv_send_represent(id):
#        """
#        """
#
#        if id:
#
#            db = current.db
#            s3db = current.s3db
#
#            table = s3db.inv_send
#            send_row = db(table.id == id).select(table.date,
#                                                 table.to_site_id,
#                                                 limitby=(0, 1)).first()
#            return SPAN(table.to_site_id.represent(send_row.to_site_id),
#                        " - ",
#                        table.date.represent(send_row.date)
#                        )
#        else:
#            return current.messages.NONE
#
#    # ---------------------------------------------------------------------
#    @staticmethod
#    def inv_send_form (r, **attr):
#        """
#            Generate a PDF of a Consignment Note
#        """
#
#        s3db = current.s3db
#
#        table = s3db.inv_recv
#        table.date.readable = True
#
#        record = table[r.id]
#        site_id = record.site_id
#        site = table.site_id.represent(site_id,False)
#
#        exporter = S3PDF()
#        return exporter(r,
#                        method="list",
#                        componentname="inv_send_item",
#                        formname="Waybill",
#                        filename="Waybill-%s" % site,
#                        report_hide_comments=True,
#                        **attr
#                       )
#
#    # -------------------------------------------------------------------------
#    @staticmethod
#    def inv_send_item_onaccept(form):
#        """
#        """
#
#        s3db = current.s3db
#
#        table = s3db.inv_send_item
#        try:
#            # Clear insufficient quantity status
#            table[form.vars.id] = dict(status = 0)
#        except:
#            pass


# =============================================================================
def inv_tabs(r):
    """
        Add an expandable set of Tabs for a Site's Inventory Tasks

        @ToDo: Make these Expand/Contract without a server-side call
    """

    T = current.T
    s3db = current.s3db
    auth = current.auth
    session = current.session
    settings = current.deployment_settings

    if settings.has_module("inv") and \
        auth.s3_has_permission("read", "inv_inv_item"):
        collapse_tabs = settings.get_inv_collapse_tabs()
        if collapse_tabs and not \
            (r.tablename == "org_office" and r.record.type == 5): # 5 = Warehouse
            # Test if the tabs are collapsed
            show_collapse = True
            show_inv = r.get_vars.show_inv
            if show_inv == "True":
                show_inv = True
            elif show_inv == "False":
                show_inv = False
            else:
                show_inv = None
            if show_inv == True or show_inv == False:
                session.s3.show_inv["%s_%s" %  (r.name, r.id)] = show_inv
            else:
                show_inv = session.s3.show_inv.get("%s_%s" %  (r.name, r.id))
        else:
            show_inv = True
            show_collapse = False

        if show_inv:
            if settings.get_inv_shipment_name() == "order":
                recv_tab = T("Orders")
            else:
                recv_tab = T("Receive")
            inv_tabs = [(T("Warehouse Stock"), "inv_item"),
                        #(T("Incoming"), "incoming/"),
                        (recv_tab, "recv"),
                        (T("Send"), "send", dict(select="sent")),
                        ]
            if settings.has_module("proc"):
                inv_tabs.append((T("Planned Procurements"), "plan"))
            if show_collapse:
                inv_tabs.append(("- %s" % T("Warehouse"),
                                 None, dict(show_inv="False")))
        else:
            inv_tabs = [("+ %s" % T("Warehouse"), "inv_item",
                        dict(show_inv="True"))]
        return inv_tabs
    else:
        return []

# =============================================================================
def inv_warehouse_rheader(r):
    """ Resource Header for warehouse stock """
    s3 = current.response.s3
    tablename, record = s3_rheader_resource(r)
    rheader = None
    if tablename == "org_organisation" or tablename == "org_office":
        rheader = s3.org_rheader(r)
    rfooter = TAG[""]()
    if "id" in record:
        as_btn = A( T("Adjust Stock"),
                      _href = URL(c = "inv",
                                  f = "adj",
                                  args = [record.id, "create"]
                                  ),
                      _class = "action-btn"
                      )
        rfooter.append(as_btn)
    else:
        ns_btn = A( T("Receive New Stock"),
                      _href = URL(c = "inv",
                                  f = "recv",
                                  args = ["create"]
                                  ),
                      _class = "action-btn"
                      )
        rfooter.append(ns_btn)

    s3.rfooter = rfooter
    return rheader

# =============================================================================
def inv_recv_crud_strings():
    """
        CRUD Strings for inv_recv which ened to be visible to menus without a
        model load
    """

    if current.deployment_settings.get_inv_shipment_name() == "order":
        recv_id_label = T("Order")
        ADD_RECV = T("Add Order")
        LIST_RECV = T("List Orders")
        current.response.s3.crud_strings["inv_recv"] = Storage(
            title_create = ADD_RECV,
            title_display = T("Order Details"),
            title_list = LIST_RECV,
            title_update = T("Edit Order"),
            title_search = T("Search Orders"),
            subtitle_create = ADD_RECV,
            subtitle_list = T("Orders"),
            label_list_button = LIST_RECV,
            label_create_button = ADD_RECV,
            label_delete_button = T("Delete Order"),
            msg_record_created = T("Order Created"),
            msg_record_modified = T("Order updated"),
            msg_record_deleted = T("Order canceled"),
            msg_list_empty = T("No Orders registered")
        )
    else:
        recv_id_label = T("Receive Shipment")
        ADD_RECV = T("Receive Shipment")
        LIST_RECV = T("List Received Shipments")
        current.response.s3.crud_strings["inv_recv"] = Storage(
            title_create = ADD_RECV,
            title_display = T("Received Shipment Details"),
            title_list = LIST_RECV,
            title_update = T("Edit Received Shipment"),
            title_search = T("Search Received Shipments"),
            subtitle_create = ADD_RECV,
            subtitle_list = T("Received Shipments"),
            label_list_button = LIST_RECV,
            label_create_button = ADD_RECV,
            label_delete_button = T("Delete Received Shipment"),
            msg_record_created = T("Shipment Created"),
            msg_record_modified = T("Received Shipment updated"),
            msg_record_deleted = T("Received Shipment canceled"),
            msg_list_empty = T("No Received Shipments")
        )
    return


# =============================================================================
def inv_send_rheader(r):
    """ Resource Header for Send """

    if r.representation == "html" and r.name == "send":
        record = r.record
        if record:

            s3db = current.s3db
            auth = current.auth
            s3 = current.response.s3

            tabs = [(T("Edit Details"), None),
                    (T("Items"), "track_item"),
                ]

            rheader_tabs = s3_rheader_tabs(r, tabs)

            table = r.table

            rheader = DIV( TABLE(
                               TR( TH("%s: " % table.date.label),
                                   table.date.represent(record.date),
                                   TH("%s: " % table.delivery_date.label),
                                   table.delivery_date.represent(record.delivery_date),
                                  ),
                               TR( TH("%s: " % table.site_id.label),
                                   table.site_id.represent(record.site_id),
                                   TH("%s: " % table.to_site_id.label),
                                   table.to_site_id.represent(record.to_site_id),
                                  ),
                               TR( TH("%s: " % table.status.label),
                                   table.status.represent(record.status),
                                   TH("%s: " % table.comments.label),
                                   TD(record.comments or "", _colspan=3)
                                  )
                                 ),
                            rheader_tabs
                            )

            rfooter = TAG[""]()

            if record.status == SHIP_STATUS_IN_PROCESS:
                if auth.s3_has_permission("update",
                                          "inv_send",
                                          record_id=record.id):
                    send_btn = A( T("Send Shipment"),
                                  _href = URL(c = "inv",
                                              f = "send_process",
                                              args = [record.id]
                                              ),
                                  _id = "send_process",
                                  _class = "action-btn"
                                  )

                    send_btn_confirm = SCRIPT("S3ConfirmClick('#send_process', '%s')"
                                              % T("Do you want to send this shipment?") )
                    rfooter.append(send_btn)
                    rfooter.append(send_btn_confirm)
            else:
                cn_btn = A( T("Waybill"),
                              _href = URL(f = "send",
                                          args = [record.id, "form"]
                                          ),
                              _class = "action-btn"
                              )
                rfooter.append(cn_btn)

                if record.status != SHIP_STATUS_CANCEL:
                    if record.status == SHIP_STATUS_SENT:
                        vars = current.request.vars
                        if "site_id" in vars and \
                            auth.s3_has_permission("update",
                                                   "org_site",
                                                   record_id=vars.site_id):
                            receive_btn = A( T("Process Received Shipment"),
                                            _href = URL(c = "inv",
                                                        f = "recv_sent",
                                                        args = [record.id],
                                                        vars = vars
                                                        ),
                                            _id = "send_receive",
                                            _class = "action-btn",
                                            _title = T("Receive this shipment")
                                            )

                            #receive_btn_confirm = SCRIPT("S3ConfirmClick('#send_receive', '%s')"
                            #                             % T("Receive this shipment?") )
                            rfooter.append(receive_btn)
                            #rheader.append(receive_btn_confirm)
                        if auth.s3_has_permission("update",
                                                  "inv_send",
                                                  record_id=record.id):
                            if "received" in vars:
                                s3db.inv_send[record.id] = \
                                    dict(status = SHIP_STATUS_RECEIVED)
                            else:
                                receive_btn = A( T("Confirm Shipment Received"),
                                                _href = URL(f = "send",
                                                            args = [record.id],
                                                            vars = dict(received = True),
                                                            ),
                                                _id = "send_receive",
                                                _class = "action-btn",
                                                _title = T("Only use this button to confirm that the shipment has been received by a destination which will not record the shipment directly into the system")
                                                )

                                receive_btn_confirm = SCRIPT("S3ConfirmClick('#send_receive', '%s')"
                                                             % T("Confirm that the shipment has been received by a destination which will not record the shipment directly into the system and confirmed as received.") )
                                rfooter.append(receive_btn)
                                rfooter.append(receive_btn_confirm)
                        if auth.s3_has_permission("delete",
                                                  "inv_send",
                                                  record_id=record.id):
                            cancel_btn = A( T("Cancel Shipment"),
                                            _href = URL(c = "inv",
                                                        f = "send_cancel",
                                                        args = [record.id]
                                                        ),
                                            _id = "send_cancel",
                                            _class = "action-btn"
                                            )

                            cancel_btn_confirm = SCRIPT("S3ConfirmClick('#send_cancel', '%s')"
                                                         % T("Do you want to cancel this sent shipment? The items will be returned to the Warehouse. This action CANNOT be undone!") )
                            rfooter.append(cancel_btn)
                            rfooter.append(cancel_btn_confirm)

            s3.rfooter = rfooter
            return rheader
    return None

# =============================================================================
def inv_recv_rheader(r):
    """ Resource Header for Receiving """

    if r.representation == "html" and r.name == "recv":
        record = r.record
        if record:

            T = current.T
            s3 = current.response.s3
            auth = current.auth

            tabs = [(T("Edit Details"), None),
                    (T("Items"), "track_item"),
                    ]

            rheader_tabs = s3_rheader_tabs(r, tabs)

            table = r.table

            rheader = DIV( TABLE(
                               TR( TH( "%s: " % table.eta.label),
                                   table.eta.represent(record.eta),
                                   TH("%s: " % table.status.label),
                                   table.status.represent(record.status),
                                  ),
                               TR( TH( "%s: " % table.date.label),
                                   table.date.represent(record.date),
                                  ),
                               TR( TH( "%s: " % table.site_id.label),
                                   table.site_id.represent(record.site_id),
                                  ),
                               TR( TH( "%s: " % table.from_site_id.label),
                                   table.from_site_id.represent(record.from_site_id),
                                  ),
                               TR( TH( "%s: " % table.sender_id.label),
                                   s3_fullname(record.sender_id),
                                   TH( "%s: " % table.recipient_id.label),
                                   s3_fullname(record.recipient_id),
                                  ),
                               TR( TH( "%s: " % table.comments.label),
                                   TD(record.comments or "", _colspan=2),
                                  ),
                                 ),
                            rheader_tabs
                            )

            rfooter = TAG[""]()

            if record.status == SHIP_STATUS_SENT:
                if auth.s3_has_permission("update",
                                          "inv_recv",
                                          record_id=record.id):
                    tracktable = current.s3db.inv_track_item
                    query = (tracktable.recv_id == record.id) & \
                            (tracktable.recv_quantity == None)
                    row = current.db(query).select(tracktable.id,
                                        limitby=(0, 1)).first()
                    if row == None:
                        recv_btn = A( T("Receive Shipment"),
                                      _href = URL(c = "inv",
                                                  f = "recv_process",
                                                  args = [record.id]
                                                  ),
                                      _id = "recv_process",
                                      _class = "action-btn"
                                      )
                        recv_btn_confirm = SCRIPT("S3ConfirmClick('#recv_process', '%s')"
                                                  % T("Do you want to receive this shipment?") )
                        rfooter.append(recv_btn)
                        rfooter.append(recv_btn_confirm)
                    else:
                        msg = T("You need to check all item quantities and allocate to bins before you can receive the shipment")
                        rfooter.append(SPAN(msg))
            else:
                grn_btn = A( T("Goods Received Note"),
                              _href = URL(f = "recv",
                                          args = [record.id, "form"]
                                          ),
                              _class = "action-btn"
                              )
                rfooter.append(grn_btn)
                dc_btn = A( T("Donation Certificate"),
                              _href = URL(f = "recv",
                                          args = [record.id, "cert"]
                                          ),
                              _class = "action-btn"
                              )
                rfooter.append(dc_btn)

                if record.status == SHIP_STATUS_RECEIVED:
                    if current.auth.s3_has_permission("delete",
                                                      "inv_recv",
                                                      record_id=record.id):
                        cancel_btn = A( T("Cancel Shipment"),
                                        _href = URL(c = "inv",
                                                    f = "recv_cancel",
                                                    args = [record.id]
                                                    ),
                                        _id = "recv_cancel",
                                        _class = "action-btn"
                                        )

                        cancel_btn_confirm = SCRIPT("S3ConfirmClick('#recv_cancel', '%s')"
                                                     % T("Do you want to cancel this received shipment? The items will be removed from the Warehouse. This action CANNOT be undone!") )
                        rfooter.append(cancel_btn)
                        rfooter.append(cancel_btn_confirm)

            s3.rfooter = rfooter
            return rheader
    return None

# =============================================================================
class S3AdjustModel(S3Model):
    """
        A module to manage the shipment of inventory items
        - Sent Items
        - Received Items
        - And audit trail of the shipment process 
    """

    names = ["inv_adj",
             "adj_id",
             "inv_adj_item",
             "adj_item_id",
             ]

    def model(self):

        T = current.T
        db = current.db
        auth = current.auth
        s3 = current.response.s3
        settings = current.deployment_settings

        person_id = self.pr_person_id
        org_id = self.org_organisation_id
        item_id = self.supply_item_id
        inv_item_id = self.inv_item_id
        item_pack_id = self.supply_item_pack_id
        currency_type = s3.currency_type
        req_item_id = self.req_item_id

        org_site_represent = self.org_site_represent

        messages = current.messages
        NONE = messages.NONE
        UNKNOWN_OPT = messages.UNKNOWN_OPT

        s3_date_format = settings.get_L10n_date_format()
        s3_date_represent = lambda dt: S3DateTime.date_represent(dt, utc=True)

        # =====================================================================
        # Send (Outgoing / Dispatch / etc)
        #
        adjust_type = {0 : T("Shipment"),
                       1 : T("Inventory"),
                      }
        adjust_status = {0 : T("In Process"),
                         1 : T("Complete"),
                        }
        tablename = "inv_adj"
        table = self.define_table("inv_adj",
                                  person_id(name = "adjuster_id",
                                            label = T("Actioning officer"),
                                            default = auth.s3_logged_in_person(),
                                            comment = self.pr_person_comment(child="adjuster_id")),

                                  self.super_link("site_id",
                                                  "org_site",
                                                  label = T("Warehouse"),
                                                  default = auth.user.site_id if auth.is_logged_in() else None,
                                                  readable = True,
                                                  writable = True,
                                                  empty = False,
                                                  represent=org_site_represent),
                                  Field("adjustment_date",
                                        "date",
                                        label = T("Date of adjustment"),
                                        default = current.request.utcnow,
                                        writable = False,
                                        represent = s3_date_represent,
                                        widget = S3DateWidget()
                                        ),
                                  Field("status",
                                        "integer",
                                        requires = IS_NULL_OR(IS_IN_SET(adjust_status)),
                                        represent = lambda opt: adjust_status.get(opt, UNKNOWN_OPT),
                                        default = 0,
                                        label = T("Status of adjustment"),
                                        writable = False,
                                        ),
                                  Field("category",
                                        "integer",
                                        requires = IS_NULL_OR(IS_IN_SET(adjust_type)),
                                        represent = lambda opt: adjust_type.get(opt, UNKNOWN_OPT),
                                        default = 1,
                                        label = T("Type of adjustment"),
                                        writable = False,
                                        ),
                                  s3.comments(),
                                  *s3.meta_fields())
        self.configure("inv_adj",
                       onaccept = self.inv_adj_onaccept,
                      )

        # Reusable Field
        adj_id = S3ReusableField( "adj_id",
                                  db.inv_adj,
                                  sortby="date",
                                  requires = IS_NULL_OR(IS_ONE_OF(db,
                                                                  "inv_adj.id",
                                                                  self.inv_adj_represent,
                                                                  orderby="inv_adj.adjustment_date",
                                                                  sort=True)),
                                   represent = self.inv_adj_represent,
                                  label = T("Inventory Adjustment"),
                                  ondelete = "RESTRICT")

        adjust_reason = {0 : T("Unknown"),
                         1 : T("None"),
                         2 : T("Lost"),
                         3 : T("Damaged"),
                         4 : T("Expired"),
                         5 : T("Found"),
                        }

        # @todo add the optional adj_id
        tablename = "inv_adj_item"
        table = self.define_table("inv_adj_item",
                                  item_id(ondelete = "NO ACTION"),      # supply item
                                  Field("reason",
                                        "integer",
                                        required = True,
                                        requires = IS_IN_SET(adjust_reason),
                                        default = 1,
                                        represent = lambda opt: adjust_reason[opt],
                                        writable = False),
                                  inv_item_id(ondelete = "NO ACTION",
                                        writable = False),  # original inventory
                                  item_pack_id(ondelete = "NO ACTION"), # pack table
                                  Field("old_quantity",
                                        "double",
                                        label = T("Original Quantity"),
                                        default = 0,
                                        notnull = True,
                                        writable = False),
                                  Field("new_quantity",
                                        "double",
                                        label = T("Revised Quantity"),
                                        represent = self.qnty_adj_repr,
                                        ),
                                  currency_type("currency"),
                                  Field("pack_value",
                                        "double",
                                        label = T("Value per Pack")),
                                  Field("expiry_date",
                                        "date",
                                        label = T("Expiry Date"),
                                        represent = s3_date_represent,
                                        widget = S3DateWidget()
                                        ),
                                  Field("bin",
                                        "string",
                                        length = 16,
                                        ),
                                  adj_id(),
                                  s3.comments(),
                                  *s3.meta_fields()
                                  )
        # Reusable Field
        adj_item_id = S3ReusableField( "adj_item_id",
                                       db.inv_adj_item,
                                       sortby="item_id",
                                       requires = IS_NULL_OR(IS_ONE_OF(db,
                                                                  "inv_adj_item.id",
                                                                  self.inv_adj_item_represent,
                                                                  orderby="inv_adj_item.item_id",
                                                                  sort=True)),
                                       represent = self.inv_adj_item_represent,
                                       label = T("Inventory Adjustment Item"),
                                       ondelete = "RESTRICT")

        # Component
        self.add_component("inv_adj_item",
                           inv_adj="adj_id")

        return Storage(
                    adj_item_id = adj_item_id,
                    adj_id = adj_id,
                )

    # -------------------------------------------------------------------------
    @staticmethod
    def qnty_adj_repr(value):
        if value:
            return value
        else:
            return B(value)


    # ---------------------------------------------------------------------
    @staticmethod
    def inv_adj_onaccept(form):
        """
           When an adjustment record is created and it is of type inventory
           then an adj_item record for each inv_inv_item in the site will be 
           created. If needed, extra adj_item records can be created later.
        """
        s3db = current.s3db
        db = current.db
        stocktable = s3db.inv_inv_item
        adjitemtable = s3db.inv_adj_item
        adjtable = s3db.inv_adj
        adj_rec = adjtable[form.vars.id]
        if adj_rec.category == 1:
            site_id = form.vars.site_id
            # Only get stock items with a positive quantity
            query = (stocktable.site_id == site_id) & \
                    (stocktable.quantity > 0)
            inv_item_row = db(query).select()
            for inv_item in inv_item_row:
                # add an adjustment item record
                adjitemtable.insert(reason = 0,
                                    adj_id = form.vars.id,
                                    inv_item_id = inv_item.id, # original source inv_item
                                    item_id = inv_item.item_id, # the supply item
                                    item_pack_id = inv_item.item_pack_id,
                                    old_quantity = inv_item.quantity,
                                    currency = inv_item.currency,
                                    pack_value = inv_item.pack_value,
                                    expiry_date = inv_item.expiry_date,
                                    bin = inv_item.bin,
                                   )


    # ---------------------------------------------------------------------
    @staticmethod
    def inv_adj_represent(id):
        """
        """

        if id:

            db = current.db
            s3db = current.s3db

            table = s3db.inv_adj
            send_row = db(table.id == id).select(table.adjustment_date,
                                                 table.adjuster_id,
                                                 limitby=(0, 1)).first()
            return SPAN(table.adjuster_id.represent(send_row.adjuster_id),
                        " - ",
                        table.adjustment_date.represent(send_row.adjustment_date)
                        )
        else:
            return current.messages.NONE


    # ---------------------------------------------------------------------
    @staticmethod
    def inv_adj_item_represent(id):
        """
        """

        if id:

            db = current.db
            s3db = current.s3db

            table = s3db.inv_adj_item
            adj_row = db(table.id == id).select(table.item_id,
                                                 table.old_quantity,
                                                 table.new_quantity,
                                                 table.item_pack_id,
                                                 limitby=(0, 1)).first()
            return SPAN(table.item_id.represent(adj_row.item_id),
                        ": ",
                        (adj_row.new_quantity - adj_row.old_quantity),
                        " ",
                        table.item_pack_id.represent(adj_row.item_pack_id)
                        )
        else:
            return current.messages.NONE

def inv_adj_rheader(r):
    """ Resource Header for Inventory Adjustments """

    if r.representation == "html" and r.name == "adj":
        record = r.record
        if record:

            s3db = current.s3db
            auth = current.auth
            s3 = current.response.s3

            tabs = [(T("Edit Details"), None),
                    (T("Items"), "adj_item"),
                ]

            rheader_tabs = s3_rheader_tabs(r, tabs)

            table = r.table
            rheader = DIV( TABLE(
                               TR( TH("%s: " % table.adjuster_id.label),
                                   table.adjuster_id.represent(record.adjuster_id),
                                   TH("%s: " % table.adjustment_date.label),
                                   table.adjustment_date.represent(record.adjustment_date),
                                  ),
                               TR( TH("%s: " % table.site_id.label),
                                   table.site_id.represent(record.site_id),
                                   TH("%s: " % table.category.label),
                                   table.category.represent(record.category),
                                  ),
                                 ),
                            rheader_tabs
                            )

            rfooter = TAG[""]()
            if record.status == 0: # In process
                if auth.s3_has_permission("update",
                                          "inv_adj",
                                          record_id=record.id):
                    aitable = current.s3db.inv_adj_item
                    query = (aitable.adj_id == record.id) & \
                            (aitable.new_quantity == None)
                    row = current.db(query).select(aitable.id,
                                        limitby=(0, 1)).first()
                    if row == None:
                        close_btn = A( T("Close Adjustment"),
                                      _href = URL(c = "inv",
                                                  f = "adj_close",
                                                  args = [record.id]
                                                  ),
                                      _id = "adj_close",
                                      _class = "action-btn"
                                      )
                        close_btn_confirm = SCRIPT("S3ConfirmClick('#adj_close', '%s')"
                                                  % T("Do you want to close this adjustment?") )
                        rfooter.append(close_btn)
                        rfooter.append(close_btn_confirm)
                    else:
                        msg = T("You need to check all the revised quantities before you can close this adjustment")
                        rfooter.append(SPAN(msg))
            s3.rfooter = rfooter
            return rheader
    return None

# Generic function called by the duplicator methods to determine if the
# record already exists on the database.
def duplicator(job, query):
    """
      This callback will be called when importing records it will look
      to see if the record being imported is a duplicate.

      @param job: An S3ImportJob object which includes all the details
                  of the record being imported

      If the record is a duplicate then it will set the job method to update
    """
    # ignore this processing if the id is set
    if job.id:
        return

    db = current.db

    table = job.table
    _duplicate = db(query).select(table.id, limitby=(0, 1)).first()
    if _duplicate:
        job.id = _duplicate.id
        job.data.id = _duplicate.id
        job.method = job.METHOD.UPDATE

# =============================================================================
class InvItemVirtualFields:
    """ Virtual fields as dimension classes for reports """

    extra_fields = ["pack_value",
                    "quantity"
                    ]

    def total_value(self):
        """ Year/Month of the start date of the training event """
        try:
            return self.inv_inv_item.quantity * self.inv_inv_item.pack_value
        except:
            # not available
            return current.messages.NONE

# END =========================================================================
