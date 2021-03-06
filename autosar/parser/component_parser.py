import sys
from autosar.base import parseXMLFile,splitRef,parseTextNode,parseIntNode
from autosar.component import *
from autosar.parser.behavior_parser import BehaviorParser
from autosar.parser.parser_base import ElementParser

def _getDataElemNameFromComSpec(xmlElem,portInterfaceRef):
   if xmlElem.find('./DATA-ELEMENT-REF') is not None:
      dataElemRef = splitRef(xmlElem.find('./DATA-ELEMENT-REF').text)
      assert(dataElemRef is not None)
      dataElemName = dataElemRef.pop()
      tmp = '/'+'/'.join(dataElemRef)
      if portInterfaceRef == tmp:
         return dataElemName
   return None

def _getOperationNameFromComSpec(xmlElem,portInterfaceRef):
   xmlOperation=xmlElem.find('./OPERATION-REF')
   if xmlOperation is not None:
      operationRef = splitRef(xmlOperation.text)
      assert(operationRef is not None)
      operationName = operationRef.pop()
      tmp = '/'+'/'.join(operationRef)
      if portInterfaceRef == tmp:
         return operationName
   return None

class ComponentTypeParser(ElementParser):
   """
   ComponentType parser   
   """

   def __init__(self,version=3.0):
      super().__init__(version)
      if self.version >=4.0:
         self.behavior_parser = BehaviorParser(version)

      if self.version >= 3.0 and self.version < 4.0:
         self.switcher = { 'APPLICATION-SOFTWARE-COMPONENT-TYPE': self.parseSoftwareComponent,
                           'COMPLEX-DEVICE-DRIVER-COMPONENT-TYPE': self.parseSoftwareComponent,
                           'SWC-IMPLEMENTATION': self.parseSwcImplementation,
                           'COMPOSITION-TYPE': self.parseCompositionType,
                           'CALPRM-COMPONENT-TYPE': self.parseSoftwareComponent,
                           'SERVICE-COMPONENT-TYPE': self.parseSoftwareComponent
                          }
      elif self.version >= 4.0:
         self.switcher = {
            'APPLICATION-SW-COMPONENT-TYPE': self.parseSoftwareComponent,
            'SWC-IMPLEMENTATION': self.parseSwcImplementation
         }      

   def getSupportedTags(self):
      return self.switcher.keys()

   def parseElement(self, xmlElement, parent = None):
      parseFunc = self.switcher.get(xmlElement.tag)
      if parseFunc is not None:
         return parseFunc(xmlElement,parent)
      else:
         return None
                           
   def parseSoftwareComponent(self,xmlRoot,parent=None):
      componentType=None
      handledTags = ['SHORT-NAME','APPLICATION-SOFTWARE-COMPONENT-TYPE', 'COMPLEX-DEVICE-DRIVER-COMPONENT-TYPE', 'APPLICATION-SW-COMPONENT-TYPE']
      if xmlRoot.tag=='APPLICATION-SOFTWARE-COMPONENT-TYPE': #for AUTOSAR 3.x
         componentType = ApplicationSoftwareComponent(parseTextNode(xmlRoot.find('SHORT-NAME')),parent)
      elif xmlRoot.tag=='COMPLEX-DEVICE-DRIVER-COMPONENT-TYPE':
         componentType=ComplexDeviceDriverComponent(parseTextNode(xmlRoot.find('SHORT-NAME')),parent)
      elif xmlRoot.tag == 'APPLICATION-SW-COMPONENT-TYPE': #for AUTOSAR 4.x
         componentType = ApplicationSoftwareComponent(parseTextNode(xmlRoot.find('SHORT-NAME')),parent)
      elif xmlRoot.tag == 'SERVICE-COMPONENT-TYPE': 
         componentType = ServiceComponent(parseTextNode(xmlRoot.find('SHORT-NAME')),parent)
      elif xmlRoot.tag == 'CALPRM-COMPONENT-TYPE': 
         componentType = ParameterComponent(parseTextNode(xmlRoot.find('SHORT-NAME')),parent)
      else:
         raise NotImplementedError(xmlRoot.tag)
      for xmlElem in xmlRoot.findall('./*'):
         if xmlElem.tag not in handledTags: 
            if xmlElem.tag == 'PORTS':
               self.parseComponentPorts(componentType,xmlRoot)
            elif xmlElem.tag == 'INTERNAL-BEHAVIORS':
               behaviors = xmlElem.findall('./SWC-INTERNAL-BEHAVIOR')
               if len(behaviors)>1:
                  raise ValueError('%s: an SWC cannot have multiple internal behaviors'%(componentType))
               elif len(behaviors) == 1:
                  componentType.behavior = self.behavior_parser.parseSWCInternalBehavior(behaviors[0], componentType)
            else:
               print('Unhandled tag: '+xmlElem.tag, file=sys.stderr)               
      return componentType
   
   def parseComponentPorts(self,componentType,xmlRoot):
      xmlPorts=xmlRoot.find('PORTS')
      assert(xmlPorts is not None)      
      for xmlPort in xmlPorts.findall('*'):
         if(xmlPort.tag == "R-PORT-PROTOTYPE"):
            portName = xmlPort.find('SHORT-NAME').text
            portInterfaceRef = parseTextNode(xmlPort.find('REQUIRED-INTERFACE-TREF'))
            port = RequirePort(portName,portInterfaceRef,parent=componentType)                        
            if xmlPort.findall('./REQUIRED-COM-SPECS') is not None:        
               for xmlItem in xmlPort.findall('./REQUIRED-COM-SPECS/*'):
                  if xmlItem.tag == 'CLIENT-COM-SPEC':
                     operationName=_getOperationNameFromComSpec(xmlItem,portInterfaceRef)
                     comspec=OperationComSpec(operationName)
                     port.comspec.append(comspec)
                  elif xmlItem.tag == 'UNQUEUED-RECEIVER-COM-SPEC' or xmlItem.tag == 'NONQUEUED-RECEIVER-COM-SPEC':
                     dataElemName = _getDataElemNameFromComSpec(xmlItem,portInterfaceRef)
                     comspec = DataElementComSpec(dataElemName)
                     if xmlItem.find('./ALIVE-TIMEOUT') != None:
                        comspec.aliveTimeout = parseTextNode(xmlItem.find('./ALIVE-TIMEOUT'))
                     if self.version >= 4.0:
                        if xmlItem.find('./INIT-VALUE') != None:
                           comspec.initValueRef = parseTextNode(xmlItem.find('./INIT-VALUE/CONSTANT-REFERENCE/CONSTANT-REF'))
                     else:                        
                        if xmlItem.find('./INIT-VALUE-REF') != None:
                           comspec.initValueRef = parseTextNode(xmlItem.find('./INIT-VALUE-REF'))                                                
                     port.comspec.append(comspec)
                  elif xmlItem.tag == 'QUEUED-RECEIVER-COM-SPEC':
                     dataElemName = _getDataElemNameFromComSpec(xmlItem,portInterfaceRef)
                     comspec = DataElementComSpec(dataElemName)
                     if xmlItem.find('./QUEUE-LENGTH') != None:
                        comspec.queueLength = parseTextNode(xmlItem.find('./QUEUE-LENGTH'))
                     port.comspec.append(comspec)                  
                  elif xmlItem.tag == 'MODE-SWITCH-RECEIVER-COM-SPEC':
                     pass #TODO: implement later
                  elif xmlItem.tag == 'PARAMETER-REQUIRE-COM-SPEC':
                     pass #TODO: implement later
                  else:
                     raise NotImplementedError(xmlItem.tag)
            componentType.requirePorts.append(port)
         elif(xmlPort.tag == 'P-PORT-PROTOTYPE'):
            portName = xmlPort.find('SHORT-NAME').text
            portInterfaceRef = parseTextNode(xmlPort.find('PROVIDED-INTERFACE-TREF'))
            port = ProvidePort(portName,portInterfaceRef,parent=componentType)                                       
            if xmlPort.findall('./PROVIDED-COM-SPECS') is not None:
               for xmlItem in xmlPort.findall('./PROVIDED-COM-SPECS/*'):
                  if xmlItem.tag == 'SERVER-COM-SPEC':
                     operationName=_getOperationNameFromComSpec(xmlItem,portInterfaceRef)
                     comspec=OperationComSpec(operationName)
                     comspec.queueLength=parseIntNode(xmlItem.find('QUEUE-LENGTH'))
                     port.comspec.append(comspec)
                  elif xmlItem.tag == 'UNQUEUED-SENDER-COM-SPEC' or xmlItem.tag == 'NONQUEUED-SENDER-COM-SPEC':
                     dataElemName = _getDataElemNameFromComSpec(xmlItem,portInterfaceRef)
                     comspec = DataElementComSpec(dataElemName)
                     if self.version >= 4.0:
                        if xmlItem.find('./INIT-VALUE') != None:
                           comspec.initValueRef = parseTextNode(xmlItem.find('./INIT-VALUE/CONSTANT-REFERENCE/CONSTANT-REF'))
                     else:                        
                        if xmlItem.find('./INIT-VALUE-REF') != None:
                           comspec.initValueRef = parseTextNode(xmlItem.find('./INIT-VALUE-REF'))                                                
                     if xmlItem.find('./CAN-INVALIDATE') != None:
                        comspec.canInvalidate = True if parseTextNode(xmlItem.find('./CAN-INVALIDATE'))=='true' else False
                     port.comspec.append(comspec)
                  elif xmlItem.tag == 'QUEUED-SENDER-COM-SPEC':
                     dataElemName = _getDataElemNameFromComSpec(xmlItem,portInterfaceRef)
                     comspec = DataElementComSpec(dataElemName)
                     port.comspec.append(comspec)
                  else:
                     raise NotImplementedError(xmlItem.tag)
            componentType.providePorts.append(port)      

   def parseSwcImplementation(self,xmlRoot,parent=None):
      ws = parent.rootWS()
      assert(ws is not None)
      name = parseTextNode(xmlRoot.find('SHORT-NAME'))
      behaviorRef = parseTextNode(xmlRoot.find('BEHAVIOR-REF'))      
      implementation = SwcImplementation(name,behaviorRef,parent=parent)
      behavior = ws.find(behaviorRef)
      if behavior is not None:
         swc = ws.find(behavior.componentRef)
         if swc is not None:
            swc.implementation=implementation
      return implementation
   
   def parseCompositionType(self,xmlRoot,parent=None):
      """
      parses COMPOSITION-TYPE
      """
      assert(xmlRoot.tag=='COMPOSITION-TYPE')
      swc=CompositionComponent(parseTextNode(xmlRoot.find('SHORT-NAME')),parent)
      for elem in xmlRoot.findall('./*'):
         if elem.tag=='SHORT-NAME':
            continue
         if elem.tag=='PORTS':
            self.parseComponentPorts(swc,xmlRoot)
         elif elem.tag=='COMPONENTS':
            self.parseComponents(elem,swc)
         elif elem.tag=='CONNECTORS':
            self.parseConnectors(elem,swc)
         else:
            raise NotImplementedError(elem.tag)
      return swc
      
   def parseComponents(self,xmlRoot,parent):
      """
      parses <COMPONENTS>
      """
      assert(xmlRoot.tag=='COMPONENTS')
      for elem in xmlRoot.findall('./*'):
         if elem.tag=='COMPONENT-PROTOTYPE':
            name=parseTextNode(elem.find('SHORT-NAME'))
            typeRef=parseTextNode(elem.find('TYPE-TREF'))
            parent.components.append(ComponentPrototype(name,typeRef,parent))
         else:
            raise NotImplementedError(elem.tag)

   def parseConnectors(self,xmlRoot,parent=None):
      """
      parses <CONNECTORS>
      """
      assert(xmlRoot.tag=='CONNECTORS')
      for elem in xmlRoot.findall('./*'):
         if elem.tag=='ASSEMBLY-CONNECTOR-PROTOTYPE':
            name=parseTextNode(elem.find('SHORT-NAME'))
            providerComponentRef=parseTextNode(elem.find('./PROVIDER-IREF/COMPONENT-PROTOTYPE-REF'))
            providerPortRef=parseTextNode(elem.find('./PROVIDER-IREF/P-PORT-PROTOTYPE-REF'))
            requesterComponentRef=parseTextNode(elem.find('./REQUESTER-IREF/COMPONENT-PROTOTYPE-REF'))
            requesterPortRef=parseTextNode(elem.find('./REQUESTER-IREF/R-PORT-PROTOTYPE-REF'))
            parent.assemblyConnectors.append(AssemblyConnector(name, ProviderInstanceRef(providerComponentRef,providerPortRef), RequesterInstanceRef(requesterComponentRef,requesterPortRef)))
         elif elem.tag=='DELEGATION-CONNECTOR-PROTOTYPE':
            name=parseTextNode(elem.find('SHORT-NAME'))
            innerComponentRef=parseTextNode(elem.find('./INNER-PORT-IREF/COMPONENT-PROTOTYPE-REF'))
            innerPortRef=parseTextNode(elem.find('./INNER-PORT-IREF/PORT-PROTOTYPE-REF'))
            outerPortRef=parseTextNode(elem.find('./OUTER-PORT-REF'))
            parent.delegationConnectors.append(DelegationConnector(name, InnerPortInstanceRef(innerComponentRef,innerPortRef), OuterPortRef(outerPortRef)))
         else:
            raise NotImplementedError(elem.tag)
   
