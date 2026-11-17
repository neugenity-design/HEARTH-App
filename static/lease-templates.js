// Owner's existing lease wording, transcribed from the two agreement pages.
// Signature images, signer details, timestamps and certificate are excluded.
export const californiaTemplate = {
  id:'california-owner-v1',name:'Basic source lease (temporary)',version:1,
  description:'Temporary: this contains the short, 15-clause agreement found in the account. The detailed California lease is still being located; this is not the completed default template.',
  sections:[
    ['Landlord','The Landlord(s) and/or agent(s) is/are and will be referred to in this Lease Agreement as "Landlord."\n\n{{owner_name}}\n(Owner)'],
    ['Tenant','The Tenant(s) is/are: {{tenant_names}} and will be referred to in this Lease Agreement as "Tenant."'],
    ['Rental property','The Landlord agrees to rent to the Tenant the property described as a(n) {{property_type}} located at {{property_address}} which will be referred to in this Lease as the "Leased Premises."'],
    ['Term of lease agreement','The Lease Agreement will begin on {{start_date}}. {{term_end_statement}}'],
    ['Use & occupancy of property','The only person(s) living in the Leased Premises is/are: {{occupant_names}}.'],
    ['Rent due',"A. The amount of the Rent is {{monthly_rent}} to be paid Monthly.\nB. The rent is due in advance on or before day {{due_day}} of each month. The rent due date is the date the Landlord must receive the Tenant's payment."],
    ['Payments','All payments shall be made to {{owner_name}} on or before day {{due_day}} of each month. Payments should be made via the following methods:\n{{payment_methods}}'],
    ['Late fee','If the rent or any other charges are not received by the Landlord on or before {{grace_days}} days after the rent due date, Tenant must pay a late fee of {{late_fee}} in addition to the rent.'],
    ['Security deposit',"A. The Tenant(s) have paid to the Landlord a Security Deposit of {{security_deposit}}.\nB. The Security Deposit is intended to pay the cost of damages, cleaning, excessive wear and tear, and unreturned keys once the Lease Agreement has ended and/or for any unpaid charges due by reason of Tenant's default of this Lease Agreement."],
    ['Utilities & services',"A. Tenant is responsible for the following utilities and services: {{tenant_utilities}} and is required to register the utilities and services in Tenant's name. Tenant understands and agrees that essential services are to be maintained and operational at all times.\nB. Landlord will be responsible for the following utilities and services: {{landlord_utilities}}"],
    ['Maintenance and repairs','The Tenant is responsible for all repairs needed in or about the Leased Premises.'],
    ['Condition of property','A. The Tenant acknowledges that the Tenant has inspected the Leased Premises and at the commencement of this Lease Agreement, the interior and exterior of the Leased Premises, as well as all equipment and any appliances are found to be in an acceptable condition and in good working order.\nB. The Tenant agrees that neither the Landlord nor his agent have made promises regarding the condition of the Lease Premises.\nC. The Tenant agrees to return the Leased Premises to Landlord at end of the Lease Agreement in the same condition it was the beginning of the Lease Agreement.'],
    ['Ending or renewing the lease agreement','A. At the end of the Lease term, if the Landlord or the Tenant does not give any written notice to the other party to end this Lease, it will automatically continue on a month to month basis. To terminate this Lease at the end of the Lease term or any renewal thereof, the Landlord or the Tenant must give to the other party at least {{notice_days}} days prior written notice before the last day of the Lease term or any renewal thereof.'],
    ['Governing law','This Agreement shall be governed, construed and interpreted by, through and under the Laws of the State of {{governing_state}}.'],
    ['Entire agreement','NOTICE: This is an important LEGAL document.\nYou may have an attorney review the Lease Agreement prior to signing it.\n\nBy signing this Lease Agreement, the Tenant certifies that he/she has read, understood and agrees to comply with all of the terms, conditions, Rules and Regulations of this Lease.']
  ]
};
