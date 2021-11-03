# ABX Action for lifecycle of DNS records in vRA deployments
# Created by Dennis Gerolymatos and Guillermo Martinez
# Version 1.0 - 24.10.2021

import winrm, sys

def handler(context, inputs):

    event         = str(inputs["__metadata"]["eventTopicId"])    # Gets the deployment Event Topic 
    ip_raw        = inputs["addresses"]                          # Raw IP input created vy vRA IPAM
    ipaddress     = str(ip_raw[0])[2:-2]                         # Cleaned up IP
    hostname_raw  = inputs["resourceNames"]                      # Raw Hostname from deployment
    hostname      = str(hostname_raw)[2:-2]                      # Cleaned up Hostname
    cnameRecord   = inputs["customProperties"]["cnameRecord"]    # Gets CNAME value from customproperties
    DNS_Server1 = context.getSecret(inputs["dns_server1"])       # DNS server where the command will be executed
    DNS_Server2 = context.getSecret(inputs["dns_server2"])       # DNS server where the command will be executed (secondary)
    DNS_Domain = context.getSecret(inputs["domain_name"])        # DNS Domain to be updated
    Username = context.getSecret(inputs["domain_username"])      # Username with righs to perform the operation
    Password = context.getSecret(inputs["domain_password"])      # Password for the account

    #Open session to DNS Server, try DNS 1 first and failback to DNS 2 if DNS 1 connection is not succesful
    try:
        session = winrm.Session('https://'+DNS_Server1+':5986/wsman', auth=(Username,Password), transport='credssp', server_cert_validation='ignore')
        result = session.run_ps("hostname")
        print("Connected to server "+result.std_out.decode())  
    except:
        try:
            session = winrm.Session('https://'+DNS_Server2+':5986/wsman', auth=(Username,Password), transport='credssp', server_cert_validation='ignore')
            result = session.run_ps("hostname")
            print("Connected to server "+result.std_out.decode())  
        except:
            print("Connections to server "+DNS_Server1+" or "+DNS_Server2+" failed. Aborting script...")
            sys.exit(0)
    
    #Check for provision event topic
    result = event.startswith('compute.provision')
    if result == True :
      print("Creating A record and PTR for "+hostname+" "+ipaddress)
      dns_command = "Add-DnsServerResourceRecordA -ZoneName "+DNS_Domain+" -Name "+hostname+" -IPv4Address "+ipaddress+" -CreatePtr"
      result = session.run_ps(dns_command)
      print(result.std_out.decode())
      
      #creates CNAME if requested in the deployment
      if (cnameRecord) :
         print("Creating CNAME record "+cnameRecord+" pointing to "+hostname+"."+DNS_Domain)
         dns_command = "Add-DnsServerResourceRecordCname -ZoneName "+DNS_Domain+" -HostNameAlias "+hostname+"."+DNS_Domain+" -Name "+cnameRecord
         result = session.run_ps(dns_command)
         print(result.std_out.decode())

    #Check for removal event topic
    result = event.startswith('compute.removal')
    if result == True :
      print("Deleting A record and PTR for "+hostname+" "+ipaddress)
      #Remove A record
      dns_command = "Remove-DnsServerResourceRecord -ZoneName "+DNS_Domain+" -Name "+hostname+" -RRType A -force"
      result = session.run_ps(dns_command)
      print(result.std_out.decode())
      
      #search for PTR record in order to get the zone name.
      dns_command = "get-dnsserverzone | where isreverselookupzone -eq True |Get-DnsServerResourceRecord -RRType PTR | where {$_.RecordData.PtrDomainName -eq '"+hostname+"."+DNS_Domain+".'} | foreach {$_.distinguishedname}"
      result = session.run_ps(dns_command)
      content = result.std_out.decode()
      if (not content):
          print("PTR doesn't exist")
      #if PTR record was found, remove the PTR record.
      else:
          tempvar = result.std_out.decode().split(",")
          hostname2 = tempvar[0].replace('DC=','')
          zonename2 = tempvar[1].replace('DC=','')
          print("Removing PTR record "+hostname2+" in zone "+zonename2)
          dns_command = "Remove-DnsServerResourceRecord -ZoneName "+zonename2+" -Name "+hostname2+" -RRType PTR -force"
          result = session.run_ps(dns_command)
          print(result.std_out.decode())
      
      #search for a CNAME record pointing to hostname.
      dns_command = "Get-DnsServerResourceRecord -RRType CNAME -ZoneName "+DNS_Domain+" | where {$_.RecordData.hostnamealias -eq '"+hostname+"."+DNS_Domain+".'} | foreach {$_.hostname}"
      result = session.run_ps(dns_command)
      content = result.std_out.decode()
      if (not content):
          print("CNAME record not found")
         
      #if CNAME record was found, remove the CNAME record.
      else:
          print("Removing CNAME record "+result.std_out.decode())
          dns_command = "Get-DnsServerResourceRecord -RRType CNAME -ZoneName "+DNS_Domain+" | where {$_.RecordData.hostnamealias -eq '"+hostname+"."+DNS_Domain+".'} | remove-dnsserverresourcerecord -zonename "+DNS_Domain+" -force"
          result = session.run_ps(dns_command)
          print(result.std_out.decode())
        